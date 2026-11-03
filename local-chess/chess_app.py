#!/usr/bin/env python3
"""
Simple two-player local chess app using tkinter and python-chess.

Usage: Run this file. Two players can play on the same device by clicking a
source square then a destination square. Move legality, checkmate, and draws are
handled by python-chess; promoting pawns can choose a piece from the board.

Controls:
- Click or drag a piece to move it; legal destinations are highlighted.
- Use the image controls below the board to browse moves or reset the game.
"""

import tkinter as tk

THEME = {
	'background': '#ffffff',
	'panel': '#ffffff',
	'green': '#3f634b',
	'green_hover': '#52785d',
	'ink': '#000000',
	'border': '#c8c8c8',
}


def make_themed_button(parent, text, command, primary=False, image=None):
	"""Create a flat, chess-themed button for controls and dialogs."""
	if image is not None:
		button = tk.Label(
			parent, image=image, bd=0, highlightthickness=0, padx=0, pady=0,
			bg=THEME['background']
		)
		button.bind('<Button-1>', lambda _event: command())
		return button

	background = THEME['green'] if primary else '#e8dcc6'
	foreground = THEME['ink']
	hover = THEME['green_hover'] if primary else '#ddc9a9'
	button = tk.Button(
		parent,
		text=text,
		command=command,
		font=('Helvetica', 11, 'bold'),
		bg=background,
		fg=foreground,
		activebackground=hover,
		activeforeground=foreground,
		relief=tk.FLAT,
		bd=0,
		highlightthickness=1,
		highlightbackground=THEME['border'],
		padx=14,
		pady=7,
	)
	button.bind('<Enter>', lambda _event: button.configure(bg=hover))
	button.bind('<Leave>', lambda _event: button.configure(bg=background))
	return button


def show_themed_message(parent, title, message):
	"""Show a compact themed modal instead of a platform-default message box."""
	dialog = tk.Toplevel(parent)
	dialog.title(title)
	dialog.transient(parent)
	dialog.resizable(False, False)
	dialog.configure(bg=THEME['background'])
	parent.update_idletasks()
	width, height = 360, 170
	x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
	y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
	dialog.geometry(f'{width}x{height}+{x}+{y}')

	panel = tk.Frame(dialog, bg=THEME['panel'], highlightbackground=THEME['border'], highlightthickness=1)
	panel.pack(fill='both', expand=True, padx=10, pady=10)
	tk_label = tk.Label(panel, text=title, bg=THEME['panel'], fg=THEME['ink'], font=('Helvetica', 14, 'bold'))
	tk_label.pack(pady=(16, 6))
	tk_message = tk.Label(
		panel, text=message, bg=THEME['panel'], fg=THEME['ink'],
		font=('Helvetica', 11), wraplength=310, justify='center'
	)
	tk_message.pack(padx=14, pady=(0, 10))
	make_themed_button(panel, 'OK', dialog.destroy, primary=True).pack(pady=(0, 12))
	dialog.protocol('WM_DELETE_WINDOW', dialog.destroy)
	dialog.grab_set()
	parent.wait_window(dialog)

try:
	from PIL import Image, ImageTk
	PIL_AVAILABLE = True
except Exception:
	PIL_AVAILABLE = False

try:
	import chess
except Exception:
	msg = (
		"Required package 'python-chess' is not installed.\n\n"
		"Install it with:\n    pip install python-chess\n\n"
		"Then run this program again."
	)
	# Try to show a GUI error first (if tkinter available)
	try:
		root = tk.Tk()
		root.withdraw()
		show_themed_message(root, 'Missing dependency', msg)
		root.destroy()
	except Exception:
		pass
	print(msg)
	raise SystemExit(1)


UNICODE_PIECES = {
	'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
	'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚',
}

class ChessApp:
	def __init__(self, master):
		self.master = master
		master.title('Local Chess — play with a friend')
		master.configure(bg=THEME['background'])
		self.board = chess.Board()
		self.selected_sq = None

		self.square_size = 80  # Increased from 64 to 80 for higher resolution
		self.canvas = tk.Canvas(master, width=8*self.square_size, height=8*self.square_size)
		self.canvas.grid(row=0, column=0, columnspan=4)
		# bind both click and drag events
		self.canvas.bind('<Button-1>', self.on_press)
		self.canvas.bind('<B1-Motion>', self.on_drag)
		self.canvas.bind('<ButtonRelease-1>', self.on_release)
		self.canvas.bind('<Escape>', self.cancel_promotion)
		self.drag_piece = None
		self.drag_start = None
		self.drag_started = False
		self.promotion_active = False
		self.promotion_bounds = None

		# Load the board image from assets/board.png
		if PIL_AVAILABLE:
			try:
				board_img = Image.open('assets/board.png').convert('RGBA')
				# Resize to exactly fit 8x8 squares
				board_size = self.square_size * 8
				board_img = board_img.resize((board_size, board_size), Image.LANCZOS)
				self.board_image = ImageTk.PhotoImage(board_img)
			except Exception:
				self.board_image = None
				
		# try to load piece images from an `assets/` folder (wP.png, bP.png, etc.)
		# white images should be named wP.png wN.png wB.png wR.png wQ.png wK.png
		# blue/black images should be named bP.png bN.png bB.png bR.png bQ.png bK.png
		# if images are missing we fall back to unicode glyphs
		self.load_piece_images()
		self.load_ui_images()

		# move history for navigation (list of chess.Move) and current view index
		self.move_history = []
		self.view_index = 0
		self.endgame_dialog = None

		controls = tk.Frame(master, width=8 * self.square_size, height=54, bg=THEME['background'])
		controls.grid(row=1, column=0, columnspan=4, sticky='w')
		controls.grid_propagate(False)
		make_themed_button(controls, 'Take back', self.step_back, image=self.ui_images.get('take_back')).place(
			relx=90 / (8 * self.square_size), rely=0.5, anchor='center'
		)
		make_themed_button(controls, 'Redo', self.step_forward, image=self.ui_images.get('redo')).place(
			relx=250 / (8 * self.square_size), rely=0.5, anchor='center'
		)
		make_themed_button(controls, 'Reset Board', self.reset, primary=True, image=self.ui_images.get('reset')).place(
			relx=550 / (8 * self.square_size), rely=0.5, anchor='center'
		)

		self.animating_move = None

		self.draw_board()
		self.update_status()

	def draw_board(self):
		# only clear board-related items so animation items (tag 'anim') persist during animation
		self.canvas.delete('board')
		self.canvas.delete('pieces')
		self.canvas.delete('hints')
		
		# Draw the board image if available
		if hasattr(self, 'board_image'):
			self.canvas.create_image(
				self.square_size * 4,  # Center X (half of 8 squares)
				self.square_size * 4,  # Center Y (half of 8 squares)
				image=self.board_image,
				tags=('board',)
			)
		else:
			# Fallback to colored squares if board image not available
			colors = ('#F0D9B5', '#B58863')
			for rank in range(8):
				for file in range(8):
					x1 = file * self.square_size
					y1 = (7 - rank) * self.square_size
					x2 = x1 + self.square_size
					y2 = y1 + self.square_size
					color = colors[(file + rank) % 2]
					self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline='', tags=('board',))

		if self.selected_sq is not None:
			for move in self.board.legal_moves:
				if move.from_square == self.selected_sq:
					f, r = chess.square_file(move.to_square), chess.square_rank(move.to_square)
					x = f * self.square_size + self.square_size//2
					y = (7 - r) * self.square_size + self.square_size//2
					
					# All moves use same size indicator with high transparency
					radius = self.square_size * 0.2  # Unified size for all indicators
					# Create a single filled circle with high transparency (approx 80% transparent)
					self.canvas.create_oval(
						x - radius, y - radius,
						x + radius, y + radius,
						fill='#808080',
						stipple='gray25',  # more transparent pattern (~75-80% transparent)
						outline='',
						tags=('hints',)
					)


		# pieces: draw clear black/white ovals with piece glyph
		for sq in chess.SQUARES:
			piece = self.board.piece_at(sq)
			if piece:
				# Skip drawing the piece if it's being dragged or animated
				if (hasattr(self, 'dragging') and self.dragging and sq == self.drag_start) or \
				   (self.animating_move is not None and sq == self.animating_move.from_square):
					continue
				symbol = piece.symbol()
				file = chess.square_file(sq)
				rank = chess.square_rank(sq)
				ux = file * self.square_size + self.square_size//2
				uy = (7 - rank) * self.square_size + self.square_size//2
				# try to draw an image for the piece, fall back to oval+unicode glyph
				img = getattr(self, 'images', {}).get(symbol)
				if img:
					# center the image on the square
					self.canvas.create_image(ux, uy, image=img, tags=('pieces',))
				else:
					# piece color
					pc = 'white' if piece.color == chess.WHITE else 'black'
					r = int(self.square_size * 0.38)
					# oval for piece
					self.canvas.create_oval(ux-r, uy-r, ux+r, uy+r, fill=pc, outline='black', tags=('pieces',))
					# piece glyph (use unicode chess pieces for nicer visuals)
					glyph = UNICODE_PIECES.get(symbol, symbol)
					text_color = 'black' if pc == 'white' else 'white'
					self.canvas.create_text(ux, uy, text=glyph, fill=text_color, font=('Helvetica', int(self.square_size/1.6)), tags=('pieces',))


	def load_piece_images(self):
		"""Load piece images from an `assets/` directory.
		Expect files named wP.png, wN.png, wB.png, wR.png, wQ.png, wK.png for white
		and bP.png ... bK.png for black (blue variants). Missing files are ignored.
		"""
		self.images = {}
		assets = 'assets'
		# First, if a sprite sheet `assets/pieces.png` exists and PIL is available,
		# split it into a 2x6 grid. Top row -> colored (pink) pieces -> assign to
		# lowercase keys (black in the app). Bottom row -> white pieces -> uppercase keys.
		sprite_path = f"{assets}/pieces.png"
		if PIL_AVAILABLE:
			try:
				print(f"Loading sprite sheet from: {sprite_path}")
				sp = Image.open(sprite_path).convert('RGBA')
				print(f"Sprite sheet loaded successfully. Size: {sp.size}")
				w, h = sp.size
				cols = 6
				rows = 2
				cell_w = w // cols
				cell_h = h // rows
				order = ['R', 'N', 'B', 'Q', 'K', 'P']
				for row in range(rows):
					for col in range(cols):
						# Get the raw cell from sprite sheet
						cell = sp.crop((col*cell_w, row*cell_h, (col+1)*cell_w, (row+1)*cell_h))
						
						# Find the actual piece boundaries by looking for non-transparent pixels
						cell_data = cell.getdata()
						non_empty = [(i % cell_w, i // cell_w) for i, px in enumerate(cell_data) if px[3] > 0]
						if not non_empty:  # Skip empty cells
							continue
							
						# Calculate tight bounding box
						min_x = min(x for x, y in non_empty)
						max_x = max(x for x, y in non_empty)
						min_y = min(y for x, y in non_empty)
						max_y = max(y for x, y in non_empty)
						
						# Crop to actual piece with small padding
						padding = 2
						crop = cell.crop((
							max(0, min_x - padding),
							max(0, min_y - padding),
							min(cell_w, max_x + padding + 1),
							min(cell_h, max_y + padding + 1)
						))
						
						# Make pieces slightly smaller, targeting 80% of square size
						target_size = int(self.square_size * 0.8)
						
						# Create background exactly the size of the square
						new_img = Image.new('RGBA', (self.square_size, self.square_size), (0, 0, 0, 0))
						
						# Calculate new dimensions maintaining aspect ratio
						orig_w, orig_h = crop.size
						ratio = min(target_size/orig_w, target_size/orig_h)
						new_w = int(orig_w * ratio)
						new_h = int(orig_h * ratio)
						
						# Resize maintaining aspect ratio with high quality
						resized = crop.resize((new_w, new_h), Image.LANCZOS)
						
						# Calculate center position for perfect centering
						x = (self.square_size - new_w) // 2
						y = (self.square_size - new_h) // 2
						
						# Paste with transparency mask
						new_img.paste(resized, (x, y), resized)
						
						tkimg = ImageTk.PhotoImage(new_img)
						sym = order[col]
						if row == 0:
							# top row: colored -> use as black (lowercase key)
							self.images[sym.lower()] = tkimg
						else:
							# bottom row: white
							self.images[sym] = tkimg
				# if sprite loading succeeded, return
			except Exception:
				# fall back to per-file images
				pass

		# pieces by uppercase symbol (per-file fallback)
		for sym in ('P', 'N', 'B', 'R', 'Q', 'K'):
			wname = f"{assets}/w{sym}.png"
			bname = f"{assets}/b{sym}.png"
			# white key is uppercase symbol, black key is lowercase symbol
			# prefer PIL for resizing to square_size if available
			try:
				if PIL_AVAILABLE:
					img = Image.open(wname).convert('RGBA')
					img = img.resize((self.square_size, self.square_size), Image.LANCZOS)
					self.images[sym] = ImageTk.PhotoImage(img)
				else:
					self.images[sym] = tk.PhotoImage(file=wname)
			except Exception:
				# leave absent
				pass
			try:
				if PIL_AVAILABLE:
					img = Image.open(bname).convert('RGBA')
					img = img.resize((self.square_size, self.square_size), Image.LANCZOS)
					self.images[sym.lower()] = ImageTk.PhotoImage(img)
				else:
					self.images[sym.lower()] = tk.PhotoImage(file=bname)
			except Exception:
				pass

	def load_ui_images(self):
		"""Load the supplied button artwork and game-over background."""
		self.ui_images = {}
		button_assets = {
			'take_back': ('Take Back.png', 117),
			'redo': ('Redo.png', 117),
			'play_again': ('Play Again.png', 117),
			'exit': ('Exit.png', 117),
			'reset': ('Reset.png', 117),
		}
		for key, (filename, target_width) in button_assets.items():
			path = f'assets/{filename}'
			try:
				if PIL_AVAILABLE:
					image = Image.open(path).convert('RGBA')
					target_height = max(1, round(image.height * target_width / image.width))
					image = image.resize((target_width, target_height), Image.LANCZOS)
					self.ui_images[key] = ImageTk.PhotoImage(image)
				else:
					self.ui_images[key] = tk.PhotoImage(file=path)
			except Exception:
				# Keep a text-only themed button if an individual asset is unavailable.
				pass

		self.endgame_background_source = None
		try:
			if PIL_AVAILABLE:
				self.endgame_background_source = Image.open('assets/Background.png').convert('RGB')
			else:
				self.endgame_background_source = tk.PhotoImage(file='assets/Background.png')
		except Exception:
			pass

		self.promotion_background_image = None
		try:
			promotion_background_path = 'assets/promotion back ground.png'
			if PIL_AVAILABLE:
				background = Image.open(promotion_background_path).convert('RGBA')
				background = background.resize((100, 400), Image.LANCZOS)
				black_overlay = Image.new('RGB', background.size, '#000000')
				tinted = Image.blend(background.convert('RGB'), black_overlay, 0.45).convert('RGBA')
				tinted.putalpha(150)
				self.promotion_background_image = ImageTk.PhotoImage(tinted)
		except Exception:
			pass

	def get_square_from_coords(self, x, y):
		"""Convert canvas coordinates to chess square."""
		file = x // self.square_size
		rank = 7 - (y // self.square_size)
		if not (0 <= file <= 7 and 0 <= rank <= 7):
			return None
		return chess.square(file, rank)

	def on_press(self, event):
		"""Select a piece, move to a destination, or begin dragging."""
		if self.promotion_active:
			x0, y0, width, height = self.promotion_bounds
			if x0 + 10 <= event.x < x0 + width - 10 and y0 <= event.y < y0 + height:
				row = int((event.y - y0) // 100)
				if 0 <= row < 4:
					promotion_types = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)
					self.finish_promotion(promotion_types[row])
			return 'break'

		sq = self.get_square_from_coords(event.x, event.y)
		if sq is None:
			return

		piece = self.board.piece_at(sq)
		if piece is not None and piece.color == self.board.turn:
			if sq == self.selected_sq:
				self.selected_sq = None
				self.drag_start = None
				self.drag_piece = None
				self.drag_started = False
				self.canvas.delete('drag')
				self.draw_board()
				return

			# Selecting another piece replaces the current selection immediately.
			self.selected_sq = sq
			self.drag_start = sq
			self.drag_piece = piece
			self.drag_started = False
			self.draw_board()
			return

		# Empty squares and opposing pieces are possible move destinations.
		if self.selected_sq is not None:
			self.try_move(sq)

	def on_drag(self, event):
		"""Update dragged piece position."""
		if self.promotion_active:
			return 'break'

		if self.drag_piece is None or self.drag_start is None:
			return

		self.drag_started = True
		# clear any existing drag visuals
		self.canvas.delete('drag')
		# Temporarily hide the original piece while it follows the pointer.
		self.dragging = True  
		self.draw_board()
		self.dragging = False
		
		# draw the dragged piece at mouse position (image if available)
		img = getattr(self, 'images', {}).get(self.drag_piece.symbol())
		if img:
			self.canvas.create_image(event.x, event.y, image=img, tags=('drag',))
		else:
			glyph = UNICODE_PIECES.get(self.drag_piece.symbol(), '')
			self.canvas.create_text(event.x, event.y, text=glyph,
							  font=('Helvetica', int(self.square_size * 0.75)),
							  fill='black', tags=('drag',))

	def on_release(self, event):
		"""Finish a drag, or leave a click-selected piece selected."""
		if self.promotion_active:
			return 'break'

		if self.drag_piece is None or self.drag_start is None:
			return

		end_sq = self.get_square_from_coords(event.x, event.y)
		self.canvas.delete('drag')  # remove drag visuals
		self.dragging = False  # Reset dragging state

		if self.drag_started and end_sq is not None:
			self.try_move(end_sq)

		self.drag_piece = None
		self.drag_start = None
		self.drag_started = False

	def try_move(self, to_sq):
		"""Attempt to make a move to the target square."""
		from_sq = self.drag_start if self.drag_piece else self.selected_sq
		if from_sq is None:
			return

		candidate_moves = [
			move for move in self.board.legal_moves
			if move.from_square == from_sq and move.to_square == to_sq
		]
		if candidate_moves:
			promotion_moves = [move for move in candidate_moves if move.promotion]
			if promotion_moves:
				color = self.board.piece_at(from_sq).color
				promotion_piece = self.choose_promotion(color)
				if promotion_piece is None:
					self.draw_board()
					return
				move = next(move for move in promotion_moves if move.promotion == promotion_piece)
			else:
				move = candidate_moves[0]

			# record move and apply
			self.move_history = self.move_history[:self.view_index]
			self.move_history.append(move)
			self.view_index += 1
			self.selected_sq = None
			self.animate_and_push(move)
		else:
			# Invalid destinations cancel the selection without playing a sound.
			self.selected_sq = None

		self.draw_board()

	def choose_promotion(self, color):
		"""Show a centered image-only picker for the four promotion pieces."""
		self.promotion_active = True
		self.promotion_result = None
		self.promotion_wait_var = tk.BooleanVar(self.master, value=False)
		choices = (
			(chess.QUEEN, 'Q'),
			(chess.ROOK, 'R'),
			(chess.BISHOP, 'B'),
			(chess.KNIGHT, 'N'),
		)
		width, height = 100, 400
		self.canvas.update_idletasks()
		x0 = (self.canvas.winfo_width() - width) // 2
		y0 = (self.canvas.winfo_height() - height) // 2
		self.promotion_bounds = (x0, y0, width, height)
		self.canvas.create_rectangle(
			x0, y0, x0 + width, y0 + height,
			fill='#000000', stipple='gray50', outline='', tags=('promotion',)
		)
		if self.promotion_background_image is not None:
			self.canvas.create_image(
				x0, y0, image=self.promotion_background_image,
				anchor='nw', tags=('promotion',)
			)

		for index, (piece_type, symbol) in enumerate(choices):
			piece_symbol = symbol if color == chess.WHITE else symbol.lower()
			piece_image = self.images.get(piece_symbol)
			center_y = y0 + index * 100 + 50
			if piece_image is not None:
				item = self.canvas.create_image(
					x0 + width // 2, center_y,
					image=piece_image, tags=('promotion',)
				)
			else:
				glyph = UNICODE_PIECES[piece_symbol]
				item = self.canvas.create_text(
					x0 + width // 2, center_y, text=glyph,
					font=('Helvetica', 60), fill='#ffffff', tags=('promotion',)
				)
		self.canvas.tag_raise('promotion')
		self.canvas.focus_set()
		try:
			self.master.wait_variable(self.promotion_wait_var)
			return self.promotion_result
		finally:
			self.canvas.delete('promotion')
			self.canvas.configure(cursor='')
			self.promotion_active = False
			self.promotion_bounds = None

	def finish_promotion(self, piece_type):
		if self.promotion_active:
			self.promotion_result = piece_type
			self.promotion_wait_var.set(True)

	def cancel_promotion(self, _event=None):
		if self.promotion_active:
			self.finish_promotion(None)
			return 'break'

	def update_status(self):
		outcome = self.board.outcome(claim_draw=True)
		if outcome is None:
			return

		if outcome.termination == chess.Termination.CHECKMATE:
			winner = 'White' if outcome.winner == chess.WHITE else 'Black'
			message = f'Checkmate — {winner} wins'
			self.play_checkmate_sound()
		else:
			draw_messages = {
				chess.Termination.STALEMATE: 'Draw — stalemate',
				chess.Termination.INSUFFICIENT_MATERIAL: 'Draw — insufficient material',
				chess.Termination.THREEFOLD_REPETITION: 'Draw — threefold repetition',
				chess.Termination.FIVEFOLD_REPETITION: 'Draw — fivefold repetition',
				chess.Termination.SEVENTYFIVE_MOVES: 'Draw — seventy-five-move rule',
				chess.Termination.FIFTY_MOVES: 'Draw — fifty-move rule',
			}
			message = draw_messages.get(
				outcome.termination,
				f'Draw — {outcome.termination.name.replace("_", " ").lower()}'
			)

		if self.endgame_dialog is None or not self.endgame_dialog.winfo_exists():
			self.show_game_over_dialog(message)


	def play_checkmate_sound(self):
		"""Play a short distinctive sound on macOS for checkmate."""
		# Try to play a system sound non-blocking using afplay (macOS). Fallback to bell.
		try:
			import subprocess, os
			# Prefer a distinctive system sound if available
			sound_paths = [
				'/System/Library/Sounds/Glass.aiff',
				'/System/Library/Sounds/Funk.aiff',
				'/System/Library/Sounds/Pop.aiff',
			]
			for p in sound_paths:
				if os.path.exists(p):
					subprocess.Popen(['afplay', p])
					return
		except Exception:
			pass
		# fallback: play two bells with a short pause
		try:
			self.master.bell()
			self.master.after(200, self.master.bell)
		except Exception:
			# last-resort no-op
			pass


	def show_game_over_dialog(self, message):
		"""Show a centered, borderless popup for any completed game."""
		dialog = tk.Toplevel(self.master)
		self.endgame_dialog = dialog
		dialog.withdraw()
		dialog.title('Game Over')
		dialog.transient(self.master)
		dialog.overrideredirect(True)
		dialog.configure(bg=THEME['background'])
		width, height = 416, 306
		self.master.update_idletasks()
		self.canvas.update_idletasks()
		x = self.canvas.winfo_rootx() + (self.canvas.winfo_width() - width) // 2
		y = self.canvas.winfo_rooty() + (self.canvas.winfo_height() - height) // 2

		background = self.endgame_background_source
		if PIL_AVAILABLE and background is not None:
			background = background.resize((width, height), Image.LANCZOS)
			self.game_over_background_image = ImageTk.PhotoImage(background)
		elif background is not None:
			self.game_over_background_image = background
		else:
			self.game_over_background_image = None

		popup_canvas = tk.Canvas(
			dialog, width=width, height=height, bd=0, highlightthickness=0,
			bg=THEME['background']
		)
		popup_canvas.place(x=0, y=0, width=width, height=height)
		if self.game_over_background_image is not None:
			popup_canvas.create_image(0, 0, image=self.game_over_background_image, anchor='nw')
		popup_canvas.create_text(
			width // 2, 95, text=message, fill=THEME['ink'],
			font=('Helvetica', 15, 'bold'), width=width - 40, justify='center'
		)

		def on_play_again():
			dialog.destroy()
			self.endgame_dialog = None
			self.reset()

		def on_exit():
			dialog.destroy()
			self.endgame_dialog = None

		# The supplied Play Again image resets the game; Exit cancels/closes this popup.
		play_btn = make_themed_button(
			dialog, 'Reset', on_play_again, primary=True,
			image=self.ui_images.get('play_again')
		)
		play_btn.place(relx=0.31, rely=0.73, anchor='center')
		close_btn = make_themed_button(
			dialog, 'Cancel', on_exit,
			image=self.ui_images.get('exit')
		)
		close_btn.place(relx=0.69, rely=0.73, anchor='center')
		dialog.bind('<Escape>', lambda _event: dialog.destroy())
		dialog.geometry(f'{width}x{height}+{x}+{y}')
		dialog.update_idletasks()
		dialog.deiconify()
		dialog.lift()
		dialog.grab_set()

    

	def step_back(self):
		"""Step back one move in history and allow replaying from that point."""
		if self.view_index == 0:
			return
		# reconstruct board to state before view_index-1
		self.view_index -= 1
		self.board.reset()
		for m in self.move_history[:self.view_index]:
			self.board.push(m)
		self.selected_sq = None
		self.draw_board()
		self.update_status()

	def step_forward(self):
		"""Step forward one move; if at end do nothing, if behind allow replaying the next move."""
		if self.view_index >= len(self.move_history):
			return
		# push the next move
		m = self.move_history[self.view_index]
		self.view_index += 1
		# animate the move visually but ensure board also updated
		self.animate_and_push(m)

	def reset(self):
		self.board.reset()
		self.selected_sq = None
		self.drag_piece = None
		self.drag_start = None
		self.drag_started = False
		self.move_history = []
		self.view_index = 0
		self.draw_board()
		self.update_status()

	def animate_and_push(self, move, steps=12, delay=4):  # 12 steps * 4ms = 48ms total
		"""Animate the piece moving from move.from_square to move.to_square, then push the move.
		Uses smooth easing for natural movement."""
		from_sq = move.from_square
		to_sq = move.to_square
		piece = self.board.piece_at(from_sq)
		if not piece:
			return
		
		# Push the move immediately but don't redraw yet
		self.board.push(move)
			
		def ease_in_out(t):
			"""Smooth acceleration and deceleration for natural movement"""
			if t < 0.5:
				return 2.0 * t * t  # accelerate
			t = t - 1.0
			return 1.0 - 2.0 * t * t  # decelerate

		# compute start and end centers
		fx, fr = chess.square_file(from_sq), chess.square_rank(from_sq)
		tx, tr = chess.square_file(to_sq), chess.square_rank(to_sq)
		start_x = fx * self.square_size + self.square_size//2
		start_y = (7 - fr) * self.square_size + self.square_size//2
		end_x = tx * self.square_size + self.square_size//2
		end_y = (7 - tr) * self.square_size + self.square_size//2

		# create a temporary piece on canvas, prefer an image if available
		img = getattr(self, 'images', {}).get(piece.symbol())
		if img:
			# create image and move it during animation
			oval = self.canvas.create_image(start_x, start_y, image=img, tags=('anim',))
			label = None
		else:
			r = int(self.square_size * 0.38)
			pc = 'white' if piece.color == chess.WHITE else 'black'
			letter = piece.symbol().upper()
			text_color = 'black' if pc == 'white' else 'white'
			oval = self.canvas.create_oval(start_x-r, start_y-r, start_x+r, start_y+r, fill=pc, outline='black', tags=('anim',))
			label = self.canvas.create_text(start_x, start_y, text=letter, fill=text_color, font=('Helvetica', int(self.square_size/2)), tags=('anim',))

		# mark animating move so draw_board will skip drawing the source square
		self.animating_move = move
		self.draw_board()

		# animation loop
		step = 0

		def step_anim():
			nonlocal step
			step += 1
			# Apply easing to the movement
			frac = ease_in_out(step / steps)
			cx = start_x + (end_x - start_x) * frac
			cy = start_y + (end_y - start_y) * frac
			if label is None:
				# oval is an image in this case
				self.canvas.coords(oval, cx, cy)
			else:
				self.canvas.coords(oval, cx-r, cy-r, cx+r, cy+r)
				self.canvas.coords(label, cx, cy)
			if step < steps:
				self.master.after(delay, step_anim)
			else:
				# finalise: remove temp items and redraw
				self.canvas.delete('anim')
				self.animating_move = None
				self.draw_board()
				self.update_status()

		# start animation
		self.master.after(delay, step_anim)


def main():
	root = tk.Tk()
	app = ChessApp(root)
	root.mainloop()


if __name__ == '__main__':
	main()



