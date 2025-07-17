
from __future__ import annotations
from dataclasses import dataclass, field

import pickle
import random
from pathlib import Path
from enum import Enum, auto
from typing import Any, Callable, Iterator

from rich.console import Console, RenderableType, Group
from rich.panel import Panel
from rich.table import Table

MAX_SECRET_NUMBER: int = 100

class Event: ...

type EventHandler[T: Event] = Callable[[T,], None]

def NO_HANDLER(_: Event): ...
def ALL_VALID(_: Any) -> bool: return True

SAVED_LOBBY_PATH = Path("lobby.json")
SAVED_GAME_PATH = Path("game.json")

class Difficulty(Enum):
	EASY = auto()
	MEDIUM = auto()
	HARD = auto()

DIFFICULTY_SECRET_NUMBER: dict[Difficulty, int] = {
	Difficulty.EASY: 100,
	Difficulty.MEDIUM: 1_000,
	Difficulty.HARD: 100_000
}

DIFFICULTY_WIN_SCORE: dict[Difficulty, int] = {
	Difficulty.EASY: 10,
	Difficulty.MEDIUM: 100,
	Difficulty.HARD: 1000
}

@dataclass
class GameSettings:
	difficulty: Difficulty

	@staticmethod
	def default() -> GameSettings:
		return GameSettings(Difficulty.MEDIUM)

@dataclass
class GameReport:
	guess_count: int
	score: int

	@staticmethod
	def default() -> GameReport:
		return GameReport(0, 0)

def compute_score(settings: GameSettings, report: GameReport) -> int:
	return DIFFICULTY_WIN_SCORE[settings.difficulty] // report.guess_count

class Action: ...

# =================================================================================================

class Controller:
	def update(self, state: State):
		raise NotImplementedError
	
	def draw(self, state: State):
		raise NotImplementedError
	
	def on_event(self, event: Event):
		...

# =================================================================================================

class HumanController(Controller):
	_console: Console
	_event_logs: list[RenderableType]
	_lobby_actions: dict[int, LobbyAction]
	_main_menu_actions: dict[int, MainMenuAction]

	def __init__(self) -> None:
		super().__init__()
		self._console = Console()
		self._event_logs = [ ]
		self._lobby_actions = { }
		self._main_menu_actions = { }

	def _create_lobby_actions(self) -> dict[int, LobbyAction]:
		if SAVED_GAME_PATH.exists():
			return {
				0: LobbyAction.LOAD_GAME,
				1: LobbyAction.NEW_GAME,
				99: LobbyAction.QUIT,
			}
		
		else:
			return {
				0: LobbyAction.NEW_GAME,
				99: LobbyAction.QUIT,
			}
		
	def _create_main_menu_actions(self) -> dict[int, MainMenuAction]:
		if SAVED_LOBBY_PATH.exists():
			return {
				0: MainMenuAction.LOAD_LOBBY,
				1: MainMenuAction.NEW_LOBBY,
				2: MainMenuAction.CREDITS,
				99: MainMenuAction.QUIT,
			}
		
		else:
			return {
				0: MainMenuAction.NEW_LOBBY,
				2: MainMenuAction.CREDITS,
				99: MainMenuAction.QUIT,
			}
		
	def _format_lobby_action(self, action: LobbyAction) -> str:
		if action == LobbyAction.NEW_GAME: return "New Game"
		if action == LobbyAction.LOAD_GAME: return "Load Game"
		if action == LobbyAction.QUIT: return "Exit"
		raise NotImplementedError(action)
	
	def _format_main_menu_action(self, action: MainMenuAction) -> str:
		if action == MainMenuAction.NEW_LOBBY: return "New Lobby"
		if action == MainMenuAction.LOAD_LOBBY: return "Load Lobby"
		if action == MainMenuAction.CREDITS: return "Credits"
		if action == MainMenuAction.QUIT: return "Exit"
		raise NotImplementedError(action)
	
	def _format_difficulty(self, difficulty: Difficulty) -> str:
		if difficulty == Difficulty.EASY: return "easy"
		if difficulty == Difficulty.MEDIUM: return "medium"
		if difficulty == Difficulty.HARD: return "hard"
		raise NotImplementedError(difficulty)

	def _ask[T](self, prompt: str, type: Callable[[str,], T], validator: Callable[[T], bool] = ALL_VALID) -> T:
		while True:
			input = self._console.input(prompt)

			try:
				value = type(input)

			except ValueError:
				self._console.print("[red]wrong type[/red]")
				continue

			if validator(value):
				return value
			
			self._console.print("[red]wrong value[/red]")

	def _select[T](self, prompt: str, choices: dict[int, T]) -> T:
		value = self._ask(prompt, int, lambda value: value in choices)
		return choices[value]

	def _format_game_state(self, state: GameState) -> RenderableType:
		return Panel.fit(
			Group(
				f"Difficulty: {self._format_difficulty(state.settings.difficulty)}",
				f"Max: {DIFFICULTY_SECRET_NUMBER[state.settings.difficulty]}",
				f"Guess count: {state.report.guess_count}",
			)
		)

	def _format_lobby_state(self, state: LobbyState) -> RenderableType:
		return Panel.fit(
			Group(
				f"Score: {state.score}"
			), title="Lobby"
		)

	def update(self, state: State):
		if isinstance(state, Game): self.update_Game(state)
		if isinstance(state, NewGameSetup): self.update_NewGameSetup(state)
		if isinstance(state, Lobby): self.update_Lobby(state)
		if isinstance(state, MainMenu): self.update_MainMenu(state)
		if isinstance(state, Victory): self.update_Victory(state)
		if isinstance(state, Credits): self.update_Credits(state)
	
	def update_Game(self, state: Game):
		value = self._ask("(?) ", int)
		state.state.player.action = GameAction.GUESS
		state.state.player.guess = value

	def update_NewGameSetup(self, state: NewGameSetup):
		difficulties: dict[int, Difficulty] = {
			0: Difficulty.EASY, 1: Difficulty.MEDIUM, 2: Difficulty.HARD
		}
		keys: list[int] = list(difficulties.keys())
		keys.sort()
		prompt = " ".join(f"{key}:{self._format_difficulty(difficulties[key])}" for key in keys) + " (?) "
		state.settings.difficulty = self._select(prompt, difficulties)
		state.set_action(NewGameSetupAction.VALIDATE)

	def update_Lobby(self, state: Lobby):
		state.set_action(self._select("(?) ", self._lobby_actions))

	def update_MainMenu(self, state: MainMenu):
		state.set_action(self._select("(?) ", self._main_menu_actions))

	def update_Victory(self, state: Victory):
		self._console.input("Press Enter to continue...")
		state.go_next()

	def update_Credits(self, state: Credits):
		self._console.input("Press Enter to continue...")
		state.go_next()

	def draw(self, state: State):
		if isinstance(state, Game): self.draw_Game(state)
		if isinstance(state, NewGameSetup): self.draw_NewGameSetup(state)
		if isinstance(state, Lobby): self.draw_Lobby(state)
		if isinstance(state, MainMenu): self.draw_MainMenu(state)
		if isinstance(state, Victory): self.draw_Victory(state)
		if isinstance(state, Credits): self.draw_Credits(state)

	def draw_Game(self, state: Game):
		self._console.print(self._format_game_state(state.state))

		while self._event_logs:
			self._console.print(self._event_logs.pop(0))

	def draw_NewGameSetup(self, state: NewGameSetup):
		self._console.rule("Setting up new game")

	def draw_Lobby(self, state: Lobby):
		actions: dict[int, LobbyAction] = self._create_lobby_actions()
		group: list[RenderableType] = [ ]
		keys: list[int] = list(actions)
		keys.sort()

		for key in keys:
			action = actions[key]
			group.append(f"[blue]{key}. [/blue]{self._format_lobby_action(action)}")

		self._lobby_actions = actions
		self._console.print(self._format_lobby_state(state.state))
		self._console.print(Panel.fit(Group(*group)))

	def draw_MainMenu(self, state: MainMenu):
		actions: dict[int, MainMenuAction] = self._create_main_menu_actions()
		group: list[RenderableType] = [ ]
		keys: list[int] = list(actions)
		keys.sort()

		for key in keys:
			action = actions[key]
			group.append(f"[blue]{key}. [/blue]{self._format_main_menu_action(action)}")

		self._main_menu_actions = actions
		self._console.print(Panel.fit(Group(*group), title="Guess the Number"))

	def draw_Victory(self, state: Victory):
		self._console.print(Panel.fit(
			Group(
				f"difficulty: {self._format_difficulty(state.settings.difficulty)}, score: {state.report.score}",
				"Victory! \\^-^/"
			)
		))

	def draw_Credits(self, state: Credits):
		table = Table(*state.get_column_names())

		for row in state.get_credits():
			table.add_row(*row)

		self._console.print(table)

	def on_event(self, event: Event):
		if isinstance(event, GuessTooHigh):
			self._event_logs.append("[orange](v)[/orange] Guess is too high")

		if isinstance(event, GuessTooLow):
			self._event_logs.append("[orange](^)[/orange] Guess is too low")

# =================================================================================================

class State:
	def draw(self):
		raise NotImplementedError

	def update(self, mainloop: MainLoop):
		raise NotImplementedError

# =================================================================================================

class GameEvent(Event): ...

class GuessTooHigh(GameEvent): ...
class GuessTooLow(GameEvent): ...

@dataclass
class PlayerWin(GameEvent):
	report: GameReport

class GameAction(Action, Enum):
	GUESS = auto()
	QUIT = auto()

@dataclass
class Player:
	guess: int
	action: GameAction|None

	@staticmethod
	def default() -> Player:
		return Player(0, None)

@dataclass
class GameState:
	secret_number: int
	player: Player
	settings: GameSettings
	report: GameReport

	@staticmethod
	def default() -> GameState:
		return GameState(
			0, Player.default(),
			GameSettings.default(), GameReport.default()
		)

@dataclass
class Game(State):
	_controller: Controller
	_state: GameState = field(default_factory=GameState.default)
	_event_handler: EventHandler[GameEvent] = NO_HANDLER

	@property
	def player(self) -> Player:
		return self._state.player

	@property
	def secret_number(self) -> int:
		return self._state.secret_number
	
	@property
	def settings(self) -> GameSettings:
		return self._state.settings
	
	@property
	def state(self) -> GameState:
		return self._state

	def initialize(self, settings: GameSettings):
		self._state = GameState.default()
		self._state.settings = settings
		self._state.secret_number = random.randint(0, DIFFICULTY_SECRET_NUMBER[settings.difficulty])

	def draw(self):
		self._controller.draw(self)

	def update(self, mainloop: MainLoop):
		self._action = None
		self._controller.update(self)
		self._handle_action(mainloop)

	def _handle_action(self, mainloop: MainLoop):
		if self.player.action == GameAction.GUESS:
			self._state.report.guess_count += 1
			self._check_guess(mainloop)

		if self.player.action == GameAction.QUIT:
			self.save_state()
			mainloop.pop_state()

	def save_state(self):
		with open(SAVED_GAME_PATH, "wb") as file:
			file.write(pickle.dumps(self._state))

	def load_state(self):
		with open(SAVED_GAME_PATH, "rb") as file:
			self._state = pickle.loads(file.read())

	def _check_guess(self, mainloop: MainLoop):
		if self.player.guess > self.secret_number: self._controller.on_event(GuessTooHigh())
		if self.player.guess < self.secret_number: self._controller.on_event(GuessTooLow())
	
		if self.player.guess == self.secret_number:
			self._state.report.score = compute_score(self._state.settings, self._state.report)
			self._event_handler(PlayerWin(self._state.report))
			mainloop.pop_state()
			mainloop.push_state(Victory(self._controller, self._state.settings, self._state.report))

# =================================================================================================

class NewGameSetupEvent(Event): ...

@dataclass
class NewGameSettingsValidated(NewGameSetupEvent):
	settings: GameSettings

class NewGameSetupAction(Action, Enum):
	VALIDATE = auto()

@dataclass
class NewGameSetup(State):
	_controller: Controller
	_settings: GameSettings = field(default_factory=GameSettings.default)
	_event_handler: EventHandler[NewGameSetupEvent] = NO_HANDLER
	_action: NewGameSetupAction|None = None

	def set_action(self, action: NewGameSetupAction):
		self._action = action

	@property
	def settings(self) -> GameSettings:
		return self._settings

	def draw(self):
		self._controller.draw(self)

	def update(self, mainloop: MainLoop):
		self._action = None
		self._controller.update(self)
		self._handle_action(mainloop)

	def _handle_action(self, mainloop: MainLoop):
		if self._action == NewGameSetupAction.VALIDATE:
			self._event_handler(NewGameSettingsValidated(self._settings))
			mainloop.pop_state()

# =================================================================================================

class LobbyAction(Action, Enum):
	NEW_GAME = auto()
	LOAD_GAME = auto()
	QUIT = auto()

@dataclass
class LobbyState:
	score: int

	@staticmethod
	def default() -> LobbyState:
		return LobbyState(0)

@dataclass
class Lobby(State):
	_controller: Controller
	_state: LobbyState = field(default_factory=LobbyState.default)
	_action: LobbyAction|None = None
	_game_settings: GameSettings = field(default_factory=GameSettings.default)
	_create_game: bool = False
	_enabled: bool = True

	def set_action(self, action: LobbyAction):
		self._action = action

	@property
	def state(self) -> LobbyState:
		return self._state

	def initialize(self):
		self._state = LobbyState.default()
		self._state.score = 0

	def draw(self):
		if not self._enabled: return
		self._controller.draw(self)

	def update(self, mainloop: MainLoop):
		if self._create_game:
			state = Game(self._controller, _event_handler=self._on_game_event)
			state.initialize(self._game_settings)
			mainloop.push_state(state)
			self._enabled = True
			self._create_game = False
			return

		if not self._enabled: return
		self._action = None
		self._controller.update(self)
		self._handle_actions(mainloop)

	def _on_new_game_setup_event(self, event: NewGameSetupEvent):
		if isinstance(event, NewGameSettingsValidated):
			self._game_settings = event.settings
			self._create_game = True
			self._enabled = False

	def _on_game_event(self, event: GameEvent):
		if isinstance(event, PlayerWin):
			self._state.score += event.report.score

	def _handle_actions(self, mainloop: MainLoop):
		if self._action == LobbyAction.NEW_GAME:
			state = NewGameSetup(self._controller, _event_handler=self._on_new_game_setup_event)
			mainloop.push_state(state)

		if self._action == LobbyAction.LOAD_GAME:
			state = Game(self._controller, _event_handler=self._on_game_event)
			state.load_state()
			mainloop.push_state(state)

		if self._action == LobbyAction.QUIT:
			self.save_state()
			mainloop.pop_state()

	def save_state(self):
		with open(SAVED_LOBBY_PATH, "wb") as file:
			file.write(pickle.dumps(self._state))

	def load_state(self):
		with open(SAVED_LOBBY_PATH, "rb") as file:
			self._state = pickle.loads(file.read())

# =================================================================================================

class MainMenuAction(Action, Enum):
	NEW_LOBBY = auto()
	LOAD_LOBBY = auto()
	CREDITS = auto()
	QUIT = auto()

@dataclass
class MainMenu(State):
	_controller: Controller
	_action: MainMenuAction|None = None

	def set_action(self, action: MainMenuAction):
		self._action = action

	def draw(self):
		self._controller.draw(self)

	def update(self, mainloop: MainLoop):
		self._action = None
		self._controller.update(self)
		self._handle_actions(mainloop)

	def _handle_actions(self, mainloop: MainLoop):
		if self._action == MainMenuAction.NEW_LOBBY:
			state = Lobby(self._controller)
			state.initialize()
			mainloop.push_state(state)

		if self._action == MainMenuAction.LOAD_LOBBY:
			state = Lobby(self._controller)
			state.load_state()
			mainloop.push_state(state)

		if self._action == MainMenuAction.CREDITS:
			state = Credits(self._controller)
			mainloop.push_state(state)

		if self._action == MainMenuAction.QUIT:
			mainloop.pop_state()

# =================================================================================================

@dataclass
class Victory(State):
	_controller: Controller
	_settings: GameSettings
	_report: GameReport
	_go_next: bool = False

	@property
	def settings(self) -> GameSettings:
		return self._settings
	
	@property
	def report(self) -> GameReport:
		return self._report

	def go_next(self):
		self._go_next = True

	def draw(self):
		self._controller.draw(self)

	def update(self, mainloop: MainLoop):
		self._controller.update(self)

		if self._go_next:
			mainloop.pop_state()

# =================================================================================================

@dataclass
class Credits(State):
	_controller: Controller
	_go_next: bool = False

	def go_next(self):
		self._go_next = True

	def get_column_names(self) -> tuple[str, ...]:
		return ("Name", "Role")
	
	def get_credits(self) -> Iterator[tuple[str, ...]]:
		yield ("Ryoko", "Main dev")

	def draw(self):
		self._controller.draw(self)

	def update(self, mainloop: MainLoop):
		self._controller.update(self)

		if self._go_next:
			mainloop.pop_state()

# =================================================================================================

@dataclass
class MainLoop:
	_states: list[State]

	@staticmethod
	def from_state(state: State):
		return MainLoop([ state, ])

	def run(self):
		while self._states:
			state = self._states[-1]
			state.draw()
			state.update(self)

	def pop_state(self) -> State:
		return self._states.pop()

	def push_state(self, state: State):
		self._states.append(state)

def main():
	player = HumanController()
	menu = MainMenu(player)
	mainloop = MainLoop.from_state(menu)
	mainloop.run()

if __name__ == "__main__":
	main()
