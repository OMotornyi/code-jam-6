"""
SMASH ROCK!  FASTER SWING = MORE ROCK SMASHED! This app is a pre-historically accurate
representation of Paleolithic technology!  Re-invent the wheel with this (rock)cutting-edge
simulation! A caveman workout routine guaranteed to give you chiseled slabs fast!
"""
import contextvars
from itertools import cycle
import math
from pathlib import Path
import webbrowser

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button as KivyButton
from kivy.uix.button import ButtonBehavior
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup as KivyPopup
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.textinput import TextInput
from kivy.garden.navigationdrawer import NavigationDrawer

from cursor import Cursor
from i18n import DEFAULT_LOCALE, SYSTEM_LOCALE, LOCALES, TRANSLATIONS
from mixins import RepeatingBackground, SignBorder
from stone import Chisel

FONT = contextvars.ContextVar("font")

IMAGE_PATH = Path("assets", "img")
ICON = str(IMAGE_PATH / "icon.png")
OPTIONS_BACKGROUND = str(IMAGE_PATH / "options_background.png")
CAVEMAN = tuple(str(IMAGE_PATH / "caveman" / f"{i}.png") for i in range(4))
BUTTON_NORMAL = str(IMAGE_PATH / "button" / "normal.png")
BUTTON_HOVER = str(IMAGE_PATH / "button" / "hover.png")
BUTTON_PRESSED = str(IMAGE_PATH / "button" / "pressed.png")
BURGER_NORMAL = str(IMAGE_PATH / "burger" / "normal.png")
BURGER_HOVER = str(IMAGE_PATH / "burger" / "hover.png")
BURGER_PRESSED = str(IMAGE_PATH / "burger" / "pressed.png")
PROJECT_EXTENSION = ".chisel-project"
MAX_FILENAME_LENGTH = 128
GITHUB_URL = "https://github.com/salt-die/code-jam-6/tree/master/circumstantial-companions"
CURSOR = Cursor()


def get_saves_path():
    path = Path.cwd()
    if (path / "saves").exists():
        return str(path / "saves")
    return str(path)


class Button(SignBorder, KivyButton):
    def __init__(self, text, **kwargs):
        super().__init__(text=text,
                         font_name=FONT.get(),
                         outline_color=(0, 0, 0),
                         outline_width=2,
                         halign="center",
                         valign="middle",
                         **kwargs)
        self.setup_border()
        self.bind(size=self._on_size)
        Window.bind(mouse_pos=self._on_mouse_pos)
        self.background_normal = BUTTON_NORMAL
        self.background_down = BUTTON_PRESSED

    def _on_mouse_pos(self, *args):
        if self.collide_point(*self.to_widget(*Window.mouse_pos)):
            self.background_normal = BUTTON_HOVER
        else:
            self.background_normal = BUTTON_NORMAL

    def _on_size(self, *args):
        self.text_size = self.size


class BurgerButton(ButtonBehavior, Image):
    def __init__(self):
        super().__init__(source=BURGER_NORMAL, size_hint=(None, None))
        Window.bind(mouse_pos=self._on_mouse_pos)
        self.bind(state=self._on_state, pos=self._on_mouse_pos)

    def _on_mouse_pos(self, *args, override=False):
        if self.state == "down" and not override:
            return
        if self.collide_point(*self.to_widget(*Window.mouse_pos)):
            self.source = BURGER_HOVER
        else:
            self.source = BURGER_NORMAL

    def _on_state(self, *args):
        if self.state == "down":
            self.source = BURGER_PRESSED
        else:
            self._on_mouse_pos(override=True)


class Popup(SignBorder, KivyPopup):
    def __init__(self, title, content, **kwargs):
        super().__init__(title=title,
                         title_font=FONT.get(),
                         title_size=sp(20),
                         title_align="center",
                         content=content,
                         separator_color=(0, 0, 0, 0),
                         background=BUTTON_PRESSED,
                         **kwargs)
        self.setup_border()


class InfoPopup(Popup):
    def __init__(self, title, text, *, dismissable=True, size_hint):
        layout = BoxLayout(orientation="vertical",
                           spacing=dp(34),
                           padding=(dp(20), dp(15)))
        self.label = Label(text=text,
                           font_name=FONT.get(),
                           font_size=sp(20),
                           halign="center",
                           valign="middle")
        layout.add_widget(self.label)
        self.label.bind(size=self._resize_label)

        super().__init__(title,
                         layout,
                         size_hint=size_hint,
                         auto_dismiss=dismissable)
        self._resize_label()

        if dismissable:
            btn = Button(_("Cancel"), font_size=sp(16), size_hint=(1, 0.35))
            layout.add_widget(btn)
            btn.bind(on_release=self.dismiss)

    def _resize_label(self, *args):
        self.label.text_size = self.label.size


def open_error_popup(text):
    popup = InfoPopup(_("An error has occured."), text, size_hint=(0.6, 0.5))
    popup.open()
    return popup


def open_loading_popup(text):
    popup = InfoPopup(_("Loading..."),
                      text,
                      dismissable=False,
                      size_hint=(0.6, 0.3))
    popup.open()
    return popup


class SelectionPopup(Popup):
    choice = StringProperty()

    def __init__(self, title, choices):
        layout = BoxLayout(orientation="vertical",
                           spacing=dp(34),
                           padding=(dp(20), dp(15)))
        for key, string in choices.items():
            btn = Button(string, font_size=sp(16))

            def _make_select_function(key):
                def _select(btn):
                    self.dismiss()
                    self.choice = key

                return _select

            btn.bind(on_release=_make_select_function(key))
            layout.add_widget(btn)

        super().__init__(title, layout, size_hint=(0.5, 0.8))


class ImportPopup(Popup):
    def __init__(self, chisel):
        self.chisel = chisel
        layout = BoxLayout(orientation="vertical",
                           spacing=dp(34),
                           padding=(dp(20), dp(15)))
        self.file_chooser = FileChooserListView(path=get_saves_path(),
                                                filters=[self._filter_file],
                                                size_hint=(1, 0.85))
        self.btn = Button(_("Please select a file."),
                          disabled=True,
                          font_size=sp(16),
                          size_hint=(1, 0.15))

        self.file_chooser.bind(path=self._change_title,
                               selection=self._change_btn_name)
        self.btn.bind(on_release=self._select_file)

        layout.add_widget(self.file_chooser)
        layout.add_widget(self.btn)

        super().__init__("", layout, size_hint=(0.7, 0.9))
        self._change_title()

    @staticmethod
    def _filter_file(folder, filename):
        return filename.endswith(PROJECT_EXTENSION)

    def _change_title(self, *args):
        path = self.file_chooser.path
        self.title = _("Import from {path}").format(path=path)

    def _change_btn_name(self, *args):
        selection = self.file_chooser.selection
        if selection:
            self.btn.text = _('Open "{filename}"').format(filename=Path(selection[0]).name)
            self.btn.disabled = False
        else:
            self.btn.text = _("Please select a file.")
            self.btn.disabled = True

    def _select_file(self, *args):
        selection = self.file_chooser.selection
        if selection:
            self.dismiss()
            Window.remove_widget(CURSOR)
            self.loading_popup = open_loading_popup(_("Importing the project."))
            Clock.schedule_once(lambda dt: self._load_file(selection[0]), 0.1)

    def _load_file(self, path):
        try:
            self.chisel.load(path)
        except (ValueError, KeyError):
            open_error_popup(_("The file could not be loaded."))
        finally:
            self.loading_popup.dismiss()
            Window.add_widget(CURSOR, "after")

    def on_dismiss(self, *args):
        self.file_chooser.cancel()


class SaveAsPopup(Popup):

    def __init__(self, chisel):
        self.chisel = chisel
        self.save_type = None
        self.choices = {
            "background": ".png " + _("(with background)"),
            "transparent": ".png " + _("(transparent)"),
            "project": PROJECT_EXTENSION,
            "all": _("All")
        }

        layout = BoxLayout(orientation="vertical",
                           spacing=dp(34),
                           padding=(dp(20), dp(15)))
        self.file_chooser = FileChooserListView(path=get_saves_path(),
                                                filters=[self._filter_file],
                                                size_hint=(1, 0.75))

        sublayout = BoxLayout(orientation="horizontal",
                              spacing=dp(10),
                              size_hint=(1, 0.1))
        self.text_input = TextInput(text="Untitled",
                                    multiline=False,
                                    font_name=FONT.get(),
                                    font_size=sp(16),
                                    size_hint_x=0.6)
        self.save_type_btn = KivyButton(text=_("Select file type"),
                                        font_name=FONT.get(),
                                        size_hint_x=0.4)
        sublayout.add_widget(self.text_input)
        sublayout.add_widget(self.save_type_btn)

        self.save_btn = Button(_("Please select a file type."),
                               disabled=True,
                               font_size=sp(16),
                               size_hint=(1, 0.15))

        self.file_chooser.bind(path=self._change_title,
                               selection=self._set_text)
        self.text_input.bind(text=self._on_text_input,
                             on_text_validate=self._save_file)
        self.save_type_btn.bind(on_release=self.open_save_type_popup)
        self.save_btn.bind(on_release=self._save_file)

        for widget in (self.file_chooser, sublayout, self.save_btn):
            layout.add_widget(widget)

        super().__init__("", layout, size_hint=(0.7, 0.9))
        self._change_title()

    @staticmethod
    def _filter_file(folder, filename):
        return (filename.endswith(PROJECT_EXTENSION)
                or filename.endswith(".png"))

    def get_maybe_shortened_filename(self):
        string = self.get_resolved_filename()
        if len(string) > 24:
            parts = string.rsplit(".", 1)
            if len(parts) > 1:
                filename, ext = parts
                return filename[:6] + "..." + filename[-5:] + "." + ext
            return parts[0][:6] + "..." + parts[0][-5:]
        return string

    def get_resolved_filename(self):
        string = self.text_input.text
        ext = self._get_file_extension()
        if ext is None:
            return string
        if not string.endswith(ext):
            string += ext
        return string

    def _change_title(self, *args):
        path = self.file_chooser.path
        self.title = _("Save to {path}").format(path=path)

    def _set_text(self, *args):
        selection = self.file_chooser.selection
        if selection:
            self.text_input.text = Path(selection[0]).name

    def _on_text_input(self, *args):
        text = self.text_input.text
        if len(text) > MAX_FILENAME_LENGTH:
            self.text_input.text = text[:MAX_FILENAME_LENGTH]
        if self.save_type:
            current_ext = self._get_file_extension()
            if current_ext == ".png" and self.text_input.text.endswith(PROJECT_EXTENSION):
                self._set_save_type(None, "project")
            elif current_ext == PROJECT_EXTENSION and self.text_input.text.endswith(".png"):
                self._set_save_type(None, "background")
        else:
            if self.text_input.text.endswith(PROJECT_EXTENSION):
                self._set_save_type(None, "project")
            elif self.text_input.text.endswith(".png"):
                self._set_save_type(None, "background")
        self._change_btn_name()

    def _change_btn_name(self, *args):
        if self.save_type is None:
            return
        self.save_btn.text = _('Save as "{filename}"').format(
            filename=self.get_maybe_shortened_filename())

    def _save_file(self, *args):
        try:
            self._do_saves()
        except OSError:
            open_error_popup(_("The file could not be saved due to an error "
                               "raised by the operating system.\nCommon "
                               "issue: Illegal characters in the file name."))
        self.dismiss()

    def open_save_type_popup(self, *args):
        popup = SelectionPopup(_("Select file type"), self.choices)
        popup.bind(choice=self._set_save_type)
        popup.open()

    def _set_save_type(self, instance, choice):
        self.save_type_btn.text = self.choices[choice]
        self.save_btn.disabled = False
        if self.save_type is not None:
            old_ext = self._get_file_extension()
            if old_ext and self.text_input.text.endswith(old_ext):
                self.text_input.text = self.text_input.text[:-len(old_ext)]
        self.save_type = choice
        new_ext = self._get_file_extension()
        if new_ext and not self.text_input.text.endswith(new_ext):
            self.text_input.text += new_ext
        self._change_btn_name()

    def _get_file_extension(self):
        extensions = {
            "background": ".png",
            "transparent": ".png",
            "project": PROJECT_EXTENSION,
            "all": None
        }
        return extensions[self.save_type]

    def _do_saves(self):
        filename = self.get_resolved_filename()
        path = Path(self.file_chooser.path)
        ext = self._get_file_extension()
        if ext is None:
            bg_path = path / (filename + ".png")
            trans_path = path / (filename + "_transparent.png")
            project_path = path / (filename + PROJECT_EXTENSION)
        else:
            bg_path = trans_path = project_path = path / filename

        bg_func = lambda: self.chisel.export_png(bg_path, transparent=False)
        trans_func = lambda: self.chisel.export_png(trans_path,
                                                    transparent=True)
        project_func = lambda: self.chisel.save(project_path)
        all_func = lambda: bg_func() or trans_func() or project_func()
        functions = {
            "background": bg_func,
            "transparent": trans_func,
            "project": project_func,
            "all": all_func
        }
        functions[self.save_type]()

    def on_dismiss(self, *args):
        self.file_chooser.cancel()


class OptionsPanel(RepeatingBackground, BoxLayout):
    def __init__(self, chisel):
        self.chisel = chisel
        super().__init__(orientation="vertical",
                         spacing=dp(31),
                         padding=(dp(20), dp(30), dp(20), dp(15)),
                         opacity=0)  # set opacity when side panel is opened
        self.setup_background(OPTIONS_BACKGROUND)

    def build(self, locale=SYSTEM_LOCALE):
        self.clear_widgets()
        if locale in LOCALES:
            TRANSLATIONS[locale].install()
        else:
            locale = DEFAULT_LOCALE
            TRANSLATIONS[DEFAULT_LOCALE].install()

        FONT.set(LOCALES[locale]["font"])

        # Title
        title = Label(text=_("Options"),
                      font_name=FONT.get(),
                      font_size=sp(30),
                      size_hint=(1, 0.05),
                      outline_color=(0, 0, 0),
                      outline_width=2)

        # Language selection
        language_btn = Button(_("Select language"),
                              font_size=sp(18),
                              size_hint=(1, None),
                              height=dp(44))
        language_btn.bind(on_release=self.open_language_popup)

        # Import
        import_btn = Button(_("Import..."),
                            font_size=sp(18),
                            size_hint=(1, None),
                            height=dp(44))
        import_btn.bind(on_release=lambda btn: ImportPopup(self.chisel).open(btn))

        # Save as
        save_as_btn = Button(_("Save as..."),
                             font_size=sp(18),
                             size_hint=(1, None),
                             height=dp(44))
        save_as_btn.bind(on_release=lambda btn: SaveAsPopup(self.chisel).open(btn))

        # Reset
        reset_btn = Button(_("Reset"),
                           font_size=sp(18),
                           size_hint=(1, None),
                           height=dp(44))
        reset_btn.bind(on_release=self.reset_chisel)

        # Source code
        src_btn = Button(_("Source code"),
                         font_size=sp(18),
                         size_hint=(1, None),
                         height=dp(44))
        src_btn.bind(on_release=lambda btn: webbrowser.open(GITHUB_URL))

        # Animation - Normal loading of an animation won't apply desired mag_filter to each
        # individual texture, so we load each frame and cycle through the textures 'by-hand'.
        images = []
        for source in CAVEMAN:
            image = Image(source=source, size_hint=(1, 1), allow_stretch=True)
            image.texture.mag_filter = 'nearest'
            images.append(image)
        images = cycle(images)

        animation = Image(source=CAVEMAN[0],
                          size_hint=(1, 1),
                          allow_stretch=True)
        animation.texture.mag_filter = 'nearest'

        def next_texture(*args):
            animation.texture = next(images).texture
        Clock.schedule_interval(next_texture, .2)

        widgets = [title,
                   language_btn,
                   import_btn,
                   save_as_btn,
                   reset_btn,
                   src_btn,
                   animation]

        for widget in widgets:
            self.add_widget(widget)

    def update_background(self, *args):
        # Overriden to snap to the right position.
        self.bg_rect.texture.uvsize = self._get_uvsize()
        self.bg_rect.texture = self.bg_rect.texture  # Required to trigger update.
        bg_width, bg_height = self._get_background_size()
        self.bg_rect.pos = (self.right - bg_width, self.y)
        self.bg_rect.size = (bg_width, bg_height)

    def open_language_popup(self, *args):
        locales = {code: info["name"] for code, info in LOCALES.items()}
        popup = SelectionPopup(_("Select language"), locales)
        popup.bind(choice=lambda instance, choice: self.build(choice))
        popup.open()

    def reset_chisel(self, *args):
        Window.remove_widget(CURSOR)
        popup = open_loading_popup(_("Resetting the canvas."))
        Clock.schedule_once(lambda dt: (self.chisel.reset()
                                        or popup.dismiss()
                                        or Window.add_widget(CURSOR, "after")), 0.1)

    def bind_to_burger(self, burger):
        def _reposition(*args):
            burger.pos = (self.right + dp(10),
                          self.top - burger.height - dp(10))
        self.bind(pos=_reposition, size=_reposition)

class ChiselApp(App):
    def build(self):
        self.icon = ICON
        Window.minimum_width, Window.minimum_height = Window.size
        root = FloatLayout()
        navdrawer = NavigationDrawer()
        navdrawer.toggle_state()
        navdrawer.anim_type = "slide_above_anim"

        self.chisel = chisel = Chisel()
        self.chisel_on_touch_down = chisel.on_touch_down
        self.chisel_on_touch_move = chisel.on_touch_move

        options_panel = OptionsPanel(chisel)
        navdrawer.add_widget(options_panel)

        burger = BurgerButton()
        burger.bind(on_release=navdrawer.toggle_state)

        rel_layout = RelativeLayout()
        rel_layout.add_widget(chisel)  # To push it when side panel is opened.
        navdrawer.add_widget(rel_layout)
        options_panel.build()
        options_panel.bind_to_burger(burger)
        navdrawer.bind(_anim_progress=self._set_side_panel_opacity)
        navdrawer.bind(_anim_progress=self.disable_chisel)

        root.add_widget(navdrawer)
        root.add_widget(burger)
        Window.add_widget(CURSOR, canvas="after")
        return root

    def _set_side_panel_opacity(self, instance, value):
        instance.side_panel.opacity = math.ceil(instance._anim_progress)

    def disable_chisel(self, instance, value):
        if instance._anim_progress > 0:
            self.chisel.on_touch_down = self.chisel.on_touch_move = lambda *args: None
        else:
            self.chisel.on_touch_down = self.chisel_on_touch_down
            self.chisel.on_touch_move = self.chisel_on_touch_move


if __name__ == "__main__":
    ChiselApp().run()
