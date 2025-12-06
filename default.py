import os
import sys
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
from login_service import AudioBookShelfService
from library_service import AudioBookShelfLibraryService
from audio_book import AudioBookPlayer
try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve

MAX_COLUMNS = 3
MAX_ROWS = 2
MAX_PER_PAGE = MAX_COLUMNS * MAX_ROWS
COVER_WIDTH = 200
COVER_HEIGHT = 200
HORIZONTAL_PADDING = 50
VERTICAL_PADDING = 50

ADDON = xbmcaddon.Addon()
CWD = ADDON.getAddonInfo('path')
ERROR_MSG = "Error"


class SettingsDialog(xbmcgui.Dialog):
	"""Dialog to collect addon settings from user"""
	
	def get_input(self, title):
		"""Get input from user"""
		return xbmcgui.Dialog().input(title)

	def get_and_store_settings(self):
		"""Prompt user for settings and store them"""
		ip = self.get_input("Enter IP Address")
		ADDON.setSetting("ipaddress", ip)

		port = self.get_input("Enter Port")
		ADDON.setSetting("port", port)

		username = self.get_input("Enter Username")
		ADDON.setSetting("username", username)

		password = self.get_input("Enter Password")
		ADDON.setSetting("password", password)


class GUI(xbmcgui.WindowXML):
	"""Main GUI for browsing and selecting audiobooks"""
	
	def __init__(self, *args, **kwargs):
		super(GUI, self).__init__(*args, **kwargs)
		self.audiobooks = kwargs.get("optional1", [])
		self.page = 0
		self.button_controls = []
		self.play_controls = []
		self.prev_button = None
		self.next_button = None
		self.last_row = False
		self.selected_index = None

	def onInit(self):
		"""Initialize the GUI"""
		xbmc.log("=== AUDIOBOOKSHELF GUI INIT STARTED ===", xbmc.LOGINFO)
		xbmc.log(f"Number of audiobooks to display: {len(self.audiobooks)}", xbmc.LOGINFO)
		xbmc.log(f"Addon path (CWD): {CWD}", xbmc.LOGINFO)
		
		# Set background
		self.set_background()
		
		# Display audiobooks
		xbmc.log("About to display audiobooks...", xbmc.LOGINFO)
		self.display_audiobooks()
		xbmc.log("=== GUI INIT COMPLETED ===", xbmc.LOGINFO)

	def clear_audiobooks(self):
		"""Clear all audiobook controls from display"""
		for button in self.button_controls:
			self.removeControl(button)
		for play_control in self.play_controls:
			self.removeControl(play_control)

		# Remove prev and next buttons if they exist
		if hasattr(self, 'prev_button') and self.prev_button:
			self.removeControl(self.prev_button)
			self.prev_button = None

		if hasattr(self, 'next_button') and self.next_button:
			self.removeControl(self.next_button)
			self.next_button = None

		# Clear lists
		self.button_controls = []
		self.play_controls = []

	def set_background(self):
		"""Set the background image"""
		try:
			bg_path = os.path.join(CWD, 'resources', 'skins', 'default', 'media', 'background.png')
			xbmc.log(f"Looking for background at: {bg_path}", xbmc.LOGINFO)
			xbmc.log(f"Background exists: {os.path.exists(bg_path)}", xbmc.LOGINFO)
			
			if os.path.exists(bg_path):
				background_control = xbmcgui.ControlImage(0, 0, 1920, 1080, bg_path)
				self.addControl(background_control)
				xbmc.log("Background added successfully", xbmc.LOGINFO)
			else:
				xbmc.log("Background file not found, continuing without it", xbmc.LOGWARNING)
		except Exception as e:
			xbmc.log(f"Error adding background: {str(e)}", xbmc.LOGERROR)

	def display_audiobooks(self):
		"""Display audiobooks for current page"""
		xbmc.log(f"=== DISPLAY_AUDIOBOOKS called for page {self.page} ===", xbmc.LOGINFO)
		
		self.clear_audiobooks()
		self.audiobooks_to_display = self.audiobooks[self.page * MAX_PER_PAGE: (self.page + 1) * MAX_PER_PAGE]
		
		xbmc.log(f"Displaying {len(self.audiobooks_to_display)} audiobooks on this page", xbmc.LOGINFO)
		
		if len(self.audiobooks_to_display) == 0:
			xbmc.log("WARNING: No audiobooks to display!", xbmc.LOGWARNING)
			dialog = xbmcgui.Dialog()
			dialog.ok("No Audiobooks", "No audiobooks found to display")
			return
		
		total_width_for_books = MAX_COLUMNS * COVER_WIDTH + (MAX_COLUMNS - 1) * HORIZONTAL_PADDING
		start_x = (1920 - total_width_for_books) // 2

		total_height_for_books = MAX_ROWS * COVER_HEIGHT + (MAX_ROWS - 1) * VERTICAL_PADDING
		start_y = (1080 - total_height_for_books) // 2

		xbmc.log(f"Grid starting position: x={start_x}, y={start_y}", xbmc.LOGINFO)

		self.create_audiobook_buttons(start_x, start_y)
		self.set_audiobook_navigation()
		
		if self.button_controls:
			xbmc.log(f"Setting focus to first button (total buttons: {len(self.button_controls)})", xbmc.LOGINFO)
			self.setFocus(self.button_controls[0])
		else:
			xbmc.log("ERROR: No button controls created!", xbmc.LOGERROR)

	def create_audiobook_buttons(self, start_x, start_y):
		"""Create button controls for audiobooks"""
		xbmc.log(f"=== CREATING AUDIOBOOK BUTTONS ===", xbmc.LOGINFO)
		
		addon_dir = xbmcaddon.Addon().getAddonInfo('path')
		play_path = os.path.join(addon_dir, 'resources', 'skins', 'default', 'media', 'play.png')
		
		xbmc.log(f"Play icon path: {play_path}", xbmc.LOGINFO)
		xbmc.log(f"Play icon exists: {os.path.exists(play_path)}", xbmc.LOGINFO)

		for row in range(MAX_ROWS):
			for column in range(MAX_COLUMNS):
				index = row * MAX_COLUMNS + column
				if index >= len(self.audiobooks_to_display):
					break

				audiobook = self.audiobooks_to_display[index]
				x_pos = start_x + (COVER_WIDTH + HORIZONTAL_PADDING) * column
				y_pos = start_y + (COVER_HEIGHT + VERTICAL_PADDING) * row

				xbmc.log(f"Creating button {index}: '{audiobook['title']}' at ({x_pos}, {y_pos})", xbmc.LOGINFO)
				xbmc.log(f"  Cover URL: {audiobook['cover_url']}", xbmc.LOGDEBUG)

				try:
					button_control = xbmcgui.ControlButton(
						x_pos, y_pos, COVER_WIDTH, COVER_HEIGHT, "",
						focusTexture=audiobook['cover_url'],
						noFocusTexture=audiobook['cover_url']
					)
					self.addControl(button_control)
					self.button_controls.append(button_control)
					xbmc.log(f"  Button {index} added successfully", xbmc.LOGDEBUG)

					if os.path.exists(play_path):
						play_control = xbmcgui.ControlImage(x_pos, y_pos, COVER_WIDTH, COVER_HEIGHT, play_path)
						self.addControl(play_control)
						self.play_controls.append(play_control)
						play_control.setVisible(False)
						xbmc.log(f"  Play overlay {index} added successfully", xbmc.LOGDEBUG)
				except Exception as e:
					xbmc.log(f"ERROR creating button {index}: {str(e)}", xbmc.LOGERROR)

		xbmc.log(f"Created {len(self.button_controls)} buttons total", xbmc.LOGINFO)

		# Create navigation buttons
		button_width = 50
		button_height = 50
		total_width_for_buttons = 2 * button_width + 150
		center_x = (1920 - total_width_for_buttons) // 2

		prev_button_x = center_x
		prev_button_y = (1080 - button_height) - 100
		next_button_x = prev_button_x + button_width + 150
		next_button_y = prev_button_y

		prev_button_image = os.path.join(addon_dir, 'resources', 'skins', 'default', 'media', 'prev.png')
		next_button_image = os.path.join(addon_dir, 'resources', 'skins', 'default', 'media', 'next.png')
		prev_button_image_focus = os.path.join(addon_dir, 'resources', 'skins', 'default', 'media', 'prevb.png')
		next_button_image_focus = os.path.join(addon_dir, 'resources', 'skins', 'default', 'media', 'nextb.png')

		xbmc.log(f"Prev button exists: {os.path.exists(prev_button_image)}", xbmc.LOGINFO)
		xbmc.log(f"Next button exists: {os.path.exists(next_button_image)}", xbmc.LOGINFO)

		try:
			self.prev_button = xbmcgui.ControlButton(
				prev_button_x, prev_button_y, button_width, button_height, "",
				focusTexture=prev_button_image_focus,
				noFocusTexture=prev_button_image
			)
			self.addControl(self.prev_button)
			xbmc.log("Prev button added", xbmc.LOGINFO)

			self.next_button = xbmcgui.ControlButton(
				next_button_x, next_button_y, button_width, button_height, "",
				focusTexture=next_button_image_focus,
				noFocusTexture=next_button_image
			)
			self.addControl(self.next_button)
			xbmc.log("Next button added", xbmc.LOGINFO)
		except Exception as e:
			xbmc.log(f"ERROR creating navigation buttons: {str(e)}", xbmc.LOGERROR)

	def set_audiobook_navigation(self):
		"""Set up keyboard/remote navigation between controls"""
		for row in range(MAX_ROWS):
			for column in range(MAX_COLUMNS):
				index = row * MAX_COLUMNS + column
				if index >= len(self.button_controls):
					break

				button = self.button_controls[index]
				above = self.button_controls[index - MAX_COLUMNS] if index - MAX_COLUMNS >= 0 else button

				below = self.button_controls[index + MAX_COLUMNS] if (index + MAX_COLUMNS) < len(self.button_controls) else button
				rows_on_current_page = -(-len(self.audiobooks_to_display) // MAX_COLUMNS)  # Ceiling division
				if row == rows_on_current_page - 1:  # Last row on current page
					below = self.next_button

				left = button if column == 0 else self.button_controls[index - 1]
				right = button if column == MAX_COLUMNS - 1 else self.button_controls[index + 1]

				button.setNavigation(above, below, left, right)

		self.prev_button.setNavigation(self.button_controls[0], self.prev_button, self.prev_button, self.next_button)
		self.next_button.setNavigation(self.button_controls[0], self.next_button, self.prev_button, self.next_button)

	def onFocus(self, controlId):
		"""Handle focus changes to show/hide play overlay"""
		for index, button in enumerate(self.button_controls):
			if index < len(self.play_controls):
				self.play_controls[index].setVisible(button.getId() == controlId)
			if button.getId() == controlId:
				self.selected_index = index

	def next_page(self):
		"""Navigate to next page of audiobooks"""
		if (self.page + 1) * MAX_PER_PAGE < len(self.audiobooks):
			self.page += 1
			self.selected_index = None
			self.display_audiobooks()

	def previous_page(self):
		"""Navigate to previous page of audiobooks"""
		if self.page > 0:
			self.page -= 1
			self.selected_index = None
			self.display_audiobooks()

	def getRealIndex(self, current_index):
		"""Convert page-relative index to absolute index"""
		current_page = self.page
		real_index = (current_page) * MAX_PER_PAGE + current_index
		return real_index

	def onAction(self, action):
		"""Handle user actions"""
		if action.getButtonCode() == 216 or action.getId() == xbmcgui.ACTION_NAV_BACK:
			self.close()
		elif action.getId() == xbmcgui.ACTION_SELECT_ITEM:
			focus_id = self.getFocusId()
			if focus_id == self.prev_button.getId():
				self.previous_page()
			elif focus_id == self.next_button.getId():
				self.next_page()
			else:
				for index, button in enumerate(self.button_controls):
					if focus_id == button.getId():
						xbmc.log(f"Selected index: {index}", xbmc.LOGINFO)
						rindex = self.getRealIndex(index)
						xbmc.log(f"Real index: {rindex}", xbmc.LOGINFO)
						self.show_audiobook_player(rindex)
						break

	def show_audiobook_player(self, index):
		"""Show the audiobook player dialog"""
		self.selected_index = index
		selected_audiobook = self.audiobooks[index]
		cover = selected_audiobook['cover_url']
		iid = selected_audiobook['id']
		
		audiobook_data = {
			'id': iid,
			'title': selected_audiobook['title'],
			'cover': cover,
			'description': selected_audiobook['description'],
			'narrator_name': selected_audiobook['narrator_name'],
			'published_year': selected_audiobook['published_year'],
			'publisher': selected_audiobook['publisher'],
			'duration': selected_audiobook['duration'],
		}
			
		dialog = AudioBookPlayer(
			'audiobook_dialog.xml', 
			xbmcaddon.Addon().getAddonInfo('path'), 
			'default', 
			'1080i', 
			**audiobook_data
		)
		dialog.doModal()
		del dialog


def download_cover(url, item_id):
	"""Download cover image to local cache"""
	try:
		# Create cache directory in addon's profile dir (writable)
		profile_path = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
		cache_dir = os.path.join(profile_path, 'covers')
		
		if not os.path.exists(cache_dir):
			xbmc.log(f"Creating cache directory: {cache_dir}", xbmc.LOGINFO)
			os.makedirs(cache_dir)
		
		cache_file = os.path.join(cache_dir, f"{item_id}.jpg")
		
		# Return cached file if it exists
		if os.path.exists(cache_file):
			xbmc.log(f"Using cached cover: {cache_file}", xbmc.LOGDEBUG)
			return cache_file
		
		# Download the cover
		xbmc.log(f"Downloading cover from {url} to {cache_file}", xbmc.LOGINFO)
		urlretrieve(url, cache_file)
		
		if os.path.exists(cache_file):
			xbmc.log(f"Cover downloaded successfully: {cache_file}", xbmc.LOGINFO)
			return cache_file
		else:
			xbmc.log(f"Cover download failed", xbmc.LOGERROR)
			return None
	except Exception as e:
		xbmc.log(f"Error downloading cover: {str(e)}", xbmc.LOGERROR)
		return None


def select_library(url, token):
	"""Let user select a library and return its audiobooks"""
	library_service = AudioBookShelfLibraryService(url, token)

	try:
		data = library_service.get_all_libraries()
		libraries = data['libraries']
		library_names = [lib['name'] for lib in libraries]

		dialog = xbmcgui.Dialog()
		selected = dialog.select('Select a Library', library_names)

		if selected != -1:
			selected_library = libraries[selected]
			items = library_service.get_library_items(selected_library['id'])
			audiobooks = []

			xbmc.log(f"Processing {len(items.get('results', []))} items from library", xbmc.LOGINFO)

			for item in items.get("results", []):
				media = item.get('media', {})
				metadata = media.get('metadata', {})
				
				cover_path = media.get('coverPath', '') or ''
				icon_id = os.path.basename(os.path.dirname(cover_path)) if cover_path else item['id']
				cover_url = f"{url}/api/items/{icon_id}/cover?token={token}"
				
				# Download cover to local cache
				xbmc.log(f"Downloading cover for: {metadata.get('title', 'Unknown')}", xbmc.LOGINFO)
				local_cover = download_cover(cover_url, item['id'])
				
				# Fallback to icon if cover download fails
				if not local_cover:
					xbmc.log(f"Cover download failed, using addon icon", xbmc.LOGWARNING)
					local_cover = os.path.join(CWD, 'resources', 'icon.png')
				
				title = metadata.get('title', 'Unknown Title')
				description = metadata.get('description', '')
				narrator_name = metadata.get('narratorName', '')
				publisher = metadata.get('publisher', '')
				published_year = metadata.get('publishedYear', '')
				duration = media.get('duration', 0.0) or 0.0
				iid = item['id']

				audiobook = {
					"id": iid,
					"title": title,
					"cover_url": local_cover,  # Use local path instead of remote URL
					"description": description,
					"narrator_name": f"Narrator: {narrator_name}" if narrator_name else "",
					"published_year": f"Year: {published_year}" if published_year else "",
					"publisher": f"Publisher: {publisher}" if publisher else "",
					"duration": duration,
				}
				audiobooks.append(audiobook)
				xbmc.log(f"Added audiobook: {title} with cover: {local_cover}", xbmc.LOGDEBUG)

			xbmc.log(f"Loaded {len(audiobooks)} audiobooks total", xbmc.LOGINFO)
			return audiobooks
	except Exception as e:
		xbmc.log(f"Error selecting library: {str(e)}", xbmc.LOGERROR)
		xbmcgui.Dialog().ok('Error', f'Failed to load library: {str(e)}')
		return []

	return []


if __name__ == '__main__':
	# Get settings
	ip_address = ADDON.getSetting('ipaddress')
	port = ADDON.getSetting('port')
	username = ADDON.getSetting('username')
	password = ADDON.getSetting('password')

	# Prompt for settings if not configured
	if not ip_address or not port or not username or not password:
		dialog = SettingsDialog()
		dialog.get_and_store_settings()
		
		# Reload settings
		ip_address = ADDON.getSetting('ipaddress')
		port = ADDON.getSetting('port')
		username = ADDON.getSetting('username')
		password = ADDON.getSetting('password')

	# Build server URL
	url = f"http://{ip_address}:{port}"
	service = AudioBookShelfService(url)

	# Check server status
	try:
		server_status = service.server_status()
		xbmc.log(f"Server status: {server_status}", xbmc.LOGINFO)
	except Exception as e:
		xbmc.log(f"Server connection failed: {str(e)}", xbmc.LOGERROR)
		xbmcgui.Dialog().ok('Error', 'Audiobookshelf server is not reachable')
		sys.exit()

	# Login
	try:
		response_data = service.login(username, password)
		token = response_data.get('token')
		if not token:
			raise ValueError("No token in response")
		xbmc.log("Successfully logged in", xbmc.LOGINFO)
	except Exception as e:
		xbmc.log(f"Login failed: {str(e)}", xbmc.LOGERROR)
		xbmcgui.Dialog().ok('Error', 'Please check your username and password')
		sys.exit()

	# Select library and show audiobooks
	audiobooks = select_library(url, token)
	
	if audiobooks:
		ui = GUI('script-mainwindow.xml', CWD, 'default', '1080i', True, optional1=audiobooks)
		ui.doModal()
		del ui
	else:
		xbmcgui.Dialog().ok('Error', 'No audiobooks found or library selection cancelled')
