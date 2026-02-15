"""
Мобильное приложение для управления заказами и складом.
ПОЛНОСТЬЮ БЕЗ EXCEL — все данные в единой JSON-базе.
ВЕРСИЯ ДЛЯ ANDROID: все пути к данным используют user_data_dir.
"""
import os
import json
import shutil
from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple

# Импорты Kivy
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.dropdown import DropDown
from kivy.graphics import Color, Rectangle, Line
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import get_color_from_hex

# Настройки окна (адаптивность для всех устройств)
try:
    from kivy.utils import platform as kivy_platform
    if kivy_platform != 'android':
        Window.size = (360, 640)
except Exception:
    Window.size = (360, 640)

# Цветовая схема: черный и желтый (золотой)
COLORS = {
    'BACKGROUND': get_color_from_hex('#0A0A0A'),      # Почти черный фон
    'CARD_BG': get_color_from_hex('#1A1A1A'),         # Темные карточки
    'BORDER': get_color_from_hex('#333333'),          # Границы
    'TEXT_PRIMARY': get_color_from_hex('#FFFFFF'),    # Белый текст
    'TEXT_SECONDARY': get_color_from_hex('#AAAAAA'),  # Серый текст
    'TEXT_HINT': get_color_from_hex('#777777'),       # Подсказки
    'YELLOW': get_color_from_hex('#FFD700'),          # Золотой основной
    'YELLOW_DARK': get_color_from_hex('#D4AF37'),     # Темно-золотой
    'YELLOW_LIGHT': get_color_from_hex('#FFF44F'),    # Светло-желтый
    'ACCENT_GREEN': get_color_from_hex('#4CAF50'),    # Акцент зеленый
    'ACCENT_RED': get_color_from_hex('#F44336'),      # Акцент красный
    'ACCENT_AMBER': get_color_from_hex('#FF9800'),    # Акцент оранжевый
}

# Адаптивные размеры для всех устройств
class Dimensions:
    PADDING = dp(16)
    SPACING = dp(12)
    BTN_HEIGHT = dp(52)
    BTN_LARGE = dp(60)
    BTN_SMALL = dp(42)
    INPUT_HEIGHT = dp(50)
    LABEL_HEIGHT = dp(32)
    CARD_HEIGHT = dp(96)
    HEADER_HEIGHT = dp(56)
    TITLE_HEIGHT = dp(40)
    SUBTITLE_HEIGHT = dp(28)
    POPUP_WIDTH = 0.92
    POPUP_HEIGHT = 0.65


def get_table_width() -> int:
    """Вычисляет адаптивную ширину таблицы для горизонтального скролла."""
    return max(int(Window.width * 1.9), 780)


class BusinessLogic:
    """Центральный модуль бизнес-логики — все расчеты оригинальные."""
    
    @staticmethod
    def calculate_percent_expenses(cost_price: float, profit: float) -> float:
        """Оригинальная формула: %Затрат = (Затраты / (Затраты + Прибыль)) × 100%"""
        expenses = cost_price - profit
        if expenses + profit > 0:
            return (expenses / (expenses + profit)) * 100
        return 0.0

    @staticmethod
    def calculate_percent_profit(cost_price: float, profit: float) -> float:
        """Оригинальная формула: %Прибыли = (Прибыль / Стоимость) × 100%"""
        if cost_price > 0:
            return (profit / cost_price) * 100
        return 0.0

    @staticmethod
    def calculate_delivery_cost(weight: float) -> int:
        """Оригинальная логика доставки."""
        if weight >= 5:
            return 100
        if weight >= 3:
            return 150
        return 200


class DataManager:
    """Управление данными с использованием user_data_dir для совместимости с Android."""
    
    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}
        self._last_save = datetime.now()
        self._profiles: Optional[Dict] = None
        self.data_dir: str = ""
        self.profiles_file: str = ""
        self.backup_dir: str = ""
        self._init_directories()

    def _init_directories(self) -> None:
        app = App.get_running_app()
        self.data_dir = app.user_data_dir
        self.profiles_file = os.path.join(self.data_dir, "profiles.json")
        self.backup_dir = os.path.join(self.data_dir, "backups")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        if not os.path.exists(self.profiles_file) or os.path.getsize(self.profiles_file) == 0:
            self._save_safe({}, self.profiles_file)

    def _create_backup(self, filepath: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{os.path.basename(filepath)}.{timestamp}.bak"
        backup_path = os.path.join(self.backup_dir, backup_name)
        try:
            if os.path.exists(filepath):
                shutil.copy2(filepath, backup_path)
            self._cleanup_old_backups()
            return backup_path
        except Exception:
            return ""

    def _cleanup_old_backups(self, days: int = 7) -> None:
        cutoff = datetime.now() - timedelta(days=days)
        for fname in os.listdir(self.backup_dir):
            if fname.endswith('.bak'):
                path = os.path.join(self.backup_dir, fname)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(path))
                    if mtime < cutoff:
                        os.remove(path)
                except Exception:
                    pass

    def _save_safe(self, data: Dict, filepath: str) -> None:
        try:
            self._create_backup(filepath)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._last_save = datetime.now()
        except Exception as e:
            print(f"[!] Ошибка сохранения {filepath}: {e}")
            raise

    def _load_safe(self, filepath: str) -> Dict:
        try:
            if not os.path.exists(filepath):
                return {}
            if os.path.getsize(filepath) == 0:
                return {}
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            backups = sorted(
                [f for f in os.listdir(self.backup_dir) if f.startswith(os.path.basename(filepath))],
                reverse=True
            )
            if backups:
                backup_path = os.path.join(self.backup_dir, backups[0])
                try:
                    with open(backup_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    return {}
            return {}
        except Exception:
            return {}

    def get_profiles(self) -> Dict:
        if self._profiles is None:
            self._profiles = self._load_safe(self.profiles_file)
        return self._profiles

    def save_profiles(self, profiles: Dict) -> None:
        self._save_safe(profiles, self.profiles_file)
        self._profiles = profiles.copy()

    def get_profile_data(self, profile_name: str) -> Dict:
        profiles = self.get_profiles()
        if profile_name not in profiles:
            profiles[profile_name] = {
                "products": [],
                "stock": {},
                "orders": [],
                "daily_stats": {},
                "next_order_number": 1
            }
            self.save_profiles(profiles)
        return profiles[profile_name]

    def update_profile_data(self, profile_name: str, data: Dict) -> None:
        profiles = self.get_profiles()
        profiles[profile_name] = data
        self.save_profiles(profiles)


class Validators:
    """Универсальные валидаторы для всех полей ввода."""
    
    @staticmethod
    def validate_positive_float(text: str, field_name: str = "Значение") -> Tuple[Optional[float], Optional[str]]:
        try:
            value = float(text.replace(',', '.').strip())
            if value <= 0:
                return None, f"{field_name} должно быть положительным"
            return value, None
        except ValueError:
            return None, f"{field_name}: введите корректное число"

    @staticmethod
    def validate_non_empty(text: str, field_name: str = "Поле") -> Tuple[Optional[str], Optional[str]]:
        value = text.strip()
        if not value:
            return None, f"{field_name} не может быть пустым"
        return value, None

    @staticmethod
    def validate_date(text: str) -> Tuple[Optional[date], Optional[str]]:
        try:
            return datetime.strptime(text.strip(), "%Y-%m-%d").date(), None
        except ValueError:
            return None, "Неверный формат даты (ГГГГ-ММ-ДД)"


class UIComponents:
    """Универсальные UI компоненты в черно-желтом стиле."""
    
    @staticmethod
    def create_popup(title: str, message: str, callback=None) -> Popup:
        content = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(18))
        
        # Заголовок
        title_label = Label(
            text=title,
            color=COLORS['YELLOW'],
            font_size=dp(20),
            bold=True,
            size_hint_y=None,
            height=dp(40),
            halign='center',
            valign='middle'
        )
        title_label.bind(size=title_label.setter('text_size'))
        content.add_widget(title_label)
        
        # Сообщение
        label = Label(
            text=message,
            color=COLORS['TEXT_PRIMARY'],
            font_size=dp(16),
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(110)
        )
        label.bind(size=label.setter('text_size'))
        content.add_widget(label)
        
        # Кнопка
        btn_layout = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(15))
        ok_btn = Button(
            text='OK',
            background_normal='',
            background_color=COLORS['YELLOW'],
            color=COLORS['BACKGROUND'],
            font_size=dp(18),
            bold=True,
            size_hint_x=1.0
        )
        btn_layout.add_widget(ok_btn)
        content.add_widget(btn_layout)
        
        popup = Popup(
            title='',
            content=content,
            size_hint=(Dimensions.POPUP_WIDTH, 0.55),
            auto_dismiss=False,
            separator_height=0
        )
        
        def close_popup(_instance):
            popup.dismiss()
            if callback:
                callback()
        
        ok_btn.bind(on_press=close_popup)
        
        # Добавляем фон к попапу
        with popup.canvas.before:
            Color(*COLORS['CARD_BG'])
            popup.rect = Rectangle(pos=popup.pos, size=popup.size)
            popup.bind(pos=lambda inst, val: setattr(inst.rect, 'pos', val))
            popup.bind(size=lambda inst, val: setattr(inst.rect, 'size', val))
        
        popup.open()
        return popup

    @staticmethod
    def create_confirmation_popup(title: str, message: str, yes_callback, no_callback=None) -> Popup:
        content = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(18))
        
        title_label = Label(
            text=title,
            color=COLORS['YELLOW'],
            font_size=dp(20),
            bold=True,
            size_hint_y=None,
            height=dp(40),
            halign='center'
        )
        title_label.bind(size=title_label.setter('text_size'))
        content.add_widget(title_label)
        
        label = Label(
            text=message,
            color=COLORS['TEXT_PRIMARY'],
            font_size=dp(16),
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(110)
        )
        label.bind(size=label.setter('text_size'))
        content.add_widget(label)
        
        btn_layout = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(15))
        
        no_btn = Button(
            text='Отмена',
            background_normal='',
            background_color=COLORS['ACCENT_RED'],
            color=COLORS['TEXT_PRIMARY'],
            font_size=dp(17),
            bold=True,
            size_hint_x=0.45
        )
        
        yes_btn = Button(
            text='Подтвердить',
            background_normal='',
            background_color=COLORS['YELLOW'],
            color=COLORS['BACKGROUND'],
            font_size=dp(17),
            bold=True,
            size_hint_x=0.45
        )
        
        popup = Popup(
            title='',
            content=content,
            size_hint=(Dimensions.POPUP_WIDTH, 0.55),
            auto_dismiss=False,
            separator_height=0
        )
        
        def on_no(_instance):
            popup.dismiss()
            if no_callback:
                no_callback()
        
        def on_yes(_instance):
            popup.dismiss()
            yes_callback()
        
        no_btn.bind(on_press=on_no)
        yes_btn.bind(on_press=on_yes)
        btn_layout.add_widget(no_btn)
        btn_layout.add_widget(yes_btn)
        content.add_widget(btn_layout)
        
        # Фон попапа
        with popup.canvas.before:
            Color(*COLORS['CARD_BG'])
            popup.rect = Rectangle(pos=popup.pos, size=popup.size)
            popup.bind(pos=lambda inst, val: setattr(inst.rect, 'pos', val))
            popup.bind(size=lambda inst, val: setattr(inst.rect, 'size', val))
        
        popup.open()
        return popup

    @staticmethod
    def create_table_header(labels: List[tuple], width: int = 800) -> BoxLayout:
        header = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(52),
            padding=[dp(12), dp(8)],
            spacing=dp(6),
            size_hint_x=None,
            width=width
        )
        
        with header.canvas.before:
            Color(*COLORS['YELLOW_DARK'])
            header.rect = Rectangle(pos=header.pos, size=header.size)
        
        def update_rect(instance, value):
            instance.rect.pos = instance.pos
            instance.rect.size = instance.size
        
        header.bind(pos=update_rect, size=update_rect)
        
        for text, width_ratio in labels:
            label = Label(
                text=text,
                font_size=dp(16),
                bold=True,
                color=COLORS['BACKGROUND'],
                size_hint_x=width_ratio,
                halign='center',
                valign='middle'
            )
            label.bind(size=label.setter('text_size'))
            header.add_widget(label)
        
        return header

    @staticmethod
    def create_back_button(target_screen: str = 'profile', text: str = 'Назад') -> Button:
        btn = Button(
            text=f'<  {text}',
            size_hint_y=None,
            height=Dimensions.BTN_HEIGHT,
            background_normal='',
            background_color=COLORS['YELLOW'],
            color=COLORS['BACKGROUND'],
            font_size=dp(18),
            bold=True,
            size_hint_x=None,
            width=dp(100)
        )
        btn.bind(on_press=lambda x: setattr(App.get_running_app().root, 'current', target_screen))
        return btn

    @staticmethod
    def create_menu_tile(title: str, screen: str) -> Button:
        btn = Button(
            text=title,
            size_hint_y=None,
            height=dp(105),
            background_normal='',
            background_color=COLORS['CARD_BG'],
            color=COLORS['YELLOW'],
            font_size=dp(16),
            bold=True,
            halign='center',
            valign='middle'
        )
        btn.bind(size=btn.setter('text_size'))
        btn.bind(on_press=lambda x, s=screen: setattr(App.get_running_app().root, 'current', s))
        
        # Добавляем границу
        with btn.canvas.after:
            Color(*COLORS['BORDER'])
            btn.border = Line(rectangle=(btn.x, btn.y, btn.width, btn.height), width=1.2)
        
        def update_border(instance, value):
            instance.border.rectangle = (instance.x, instance.y, instance.width, instance.height)
        
        btn.bind(pos=update_border, size=update_border)
        return btn

    @staticmethod
    def create_primary_button(text: str, height: int = Dimensions.BTN_HEIGHT) -> Button:
        btn = Button(
            text=text,
            size_hint_y=None,
            height=height,
            background_normal='',
            background_color=COLORS['YELLOW'],
            color=COLORS['BACKGROUND'],
            font_size=dp(19),
            bold=True
        )
        return btn

    @staticmethod
    def create_secondary_button(text: str, height: int = Dimensions.BTN_HEIGHT, color=None) -> Button:
        btn = Button(
            text=text,
            size_hint_y=None,
            height=height,
            background_normal='',
            background_color=color or COLORS['CARD_BG'],
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True
        )
        return btn

    @staticmethod
    def create_input_field(hint_text: str = '', text: str = '') -> TextInput:
        input_field = TextInput(
            hint_text=hint_text,
            text=text,
            multiline=False,
            font_size=dp(18),
            height=Dimensions.INPUT_HEIGHT,
            size_hint_y=None,
            background_normal='',
            background_color=COLORS['CARD_BG'],
            foreground_color=COLORS['TEXT_PRIMARY'],
            padding=[dp(16), dp(14)],
            cursor_color=COLORS['YELLOW'],
            hint_text_color=COLORS['TEXT_HINT'],
            write_tab=False
        )
        
        # Добавляем границу
        with input_field.canvas.after:
            Color(*COLORS['BORDER'])
            input_field.border = Line(rectangle=(input_field.x, input_field.y, input_field.width, input_field.height), width=1.5)
        
        def update_border(instance, value):
            instance.border.rectangle = (instance.x, instance.y, instance.width, instance.height)
        
        input_field.bind(pos=update_border, size=update_border)
        return input_field


class BaseScreen(Screen):
    """Базовый класс для всех экранов с общими методами."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_manager = App.get_running_app().data_manager
        self.business_logic = App.get_running_app().business_logic

    def show_popup(self, title: str, message: str, callback=None) -> None:
        UIComponents.create_popup(title, message, callback)

    def show_confirmation(self, title: str, message: str, yes_callback, no_callback=None) -> None:
        UIComponents.create_confirmation_popup(title, message, yes_callback, no_callback)

    def get_current_profile(self) -> Optional[str]:
        return App.get_running_app().current_profile

    def get_profile_data(self) -> Dict:
        profile_name = self.get_current_profile()
        if not profile_name:
            return {}
        return self.data_manager.get_profile_data(profile_name)

    def save_profile_data(self, data: Dict) -> None:
        profile_name = self.get_current_profile()
        if profile_name:
            self.data_manager.update_profile_data(profile_name, data)


class HomeScreen(BaseScreen):
    """Экран выбора профиля."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.profiles_list = None
        self.build_ui()

    def build_ui(self) -> None:
        main_layout = BoxLayout(orientation='vertical', padding=Dimensions.PADDING, spacing=Dimensions.SPACING)
        
        # Заголовок
        title = Label(
            text='УПРАВЛЕНИЕ ЗАКАЗАМИ',
            size_hint_y=None,
            height=dp(65),
            font_size=dp(26),
            bold=True,
            color=COLORS['YELLOW'],
            halign='center',
            valign='middle'
        )
        title.bind(size=title.setter('text_size'))
        main_layout.add_widget(title)
        
        # Подзаголовок
        subtitle = Label(
            text='Товары, склад и заказы',
            size_hint_y=None,
            height=dp(30),
            font_size=dp(16),
            color=COLORS['TEXT_SECONDARY'],
            halign='center',
            valign='middle'
        )
        subtitle.bind(size=subtitle.setter('text_size'))
        main_layout.add_widget(subtitle)
        
        # Список профилей
        scroll = ScrollView(size_hint_y=0.55)
        self.profiles_list = GridLayout(cols=1, spacing=dp(12), size_hint_y=None, padding=[0, dp(5)])
        self.profiles_list.bind(minimum_height=self.profiles_list.setter('height'))
        scroll.add_widget(self.profiles_list)
        main_layout.add_widget(scroll)
        
        # Кнопка создания профиля
        btn_create = UIComponents.create_primary_button('СОЗДАТЬ НОВЫЙ ПРОФИЛЬ', height=dp(58))
        btn_create.bind(on_press=self.show_create_profile)
        main_layout.add_widget(btn_create)
        
        # Кнопка выхода
        btn_exit = UIComponents.create_secondary_button('ВЫЙТИ ИЗ ПРИЛОЖЕНИЯ', height=dp(50), color=COLORS['ACCENT_RED'])
        btn_exit.bind(on_press=lambda x: App.get_running_app().stop())
        main_layout.add_widget(btn_exit)
        
        self.add_widget(main_layout)
        self.load_profiles()

    def load_profiles(self) -> None:
        self.profiles_list.clear_widgets()
        profiles = self.data_manager.get_profiles()
        
        if not profiles:
            empty_label = Label(
                text='НЕТ ПРОФИЛЕЙ',
                size_hint_y=None,
                height=dp(60),
                color=COLORS['TEXT_SECONDARY'],
                font_size=dp(22),
                bold=True,
                halign='center',
                valign='middle'
            )
            empty_label.bind(size=empty_label.setter('text_size'))
            self.profiles_list.add_widget(empty_label)
            
            hint_label = Label(
                text='Нажмите "Создать новый профиль" чтобы начать работу',
                size_hint_y=None,
                height=dp(45),
                color=COLORS['TEXT_HINT'],
                font_size=dp(15),
                halign='center',
                valign='middle',
                italic=True
            )
            hint_label.bind(size=hint_label.setter('text_size'))
            self.profiles_list.add_widget(hint_label)
            return
        
        for profile_name in sorted(profiles.keys()):
            profile_container = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(62),
                spacing=dp(10)
            )
            
            btn = Button(
                text=profile_name,
                size_hint_x=0.8,
                background_normal='',
                background_color=COLORS['CARD_BG'],
                color=COLORS['YELLOW'],
                font_size=dp(18),
                bold=True
            )
            btn.bind(on_press=lambda instance, name=profile_name: self.select_profile(name))
            
            del_btn = Button(
                text='УДАЛИТЬ',
                size_hint_x=0.2,
                size_hint_y=None,
                height=dp(44),
                background_normal='',
                background_color=COLORS['ACCENT_RED'],
                color=COLORS['TEXT_PRIMARY'],
                font_size=dp(14),
                bold=True
            )
            del_btn.bind(on_press=lambda instance, name=profile_name: self.confirm_delete_profile(name))
            
            profile_container.add_widget(btn)
            profile_container.add_widget(del_btn)
            self.profiles_list.add_widget(profile_container)

    def select_profile(self, profile_name: str) -> None:
        app = App.get_running_app()
        app.current_profile = profile_name
        app.profile_data = self.data_manager.get_profile_data(profile_name)
        self.manager.current = 'profile'

    def confirm_delete_profile(self, profile_name: str) -> None:
        self.show_confirmation(
            title='УДАЛЕНИЕ ПРОФИЛЯ',
            message=f'Вы уверены, что хотите удалить профиль "{profile_name}"?\n'
                    f'Все данные будут безвозвратно удалены.',
            yes_callback=lambda: self.delete_profile(profile_name)
        )

    def delete_profile(self, profile_name: str) -> None:
        profiles = self.data_manager.get_profiles()
        if profile_name not in profiles:
            self.show_popup('ОШИБКА', 'Профиль не найден')
            return
        
        del profiles[profile_name]
        self.data_manager.save_profiles(profiles)
        
        app = App.get_running_app()
        if app.current_profile == profile_name:
            app.current_profile = None
            app.profile_data = {}
        
        self.show_popup(
            'УСПЕХ',
            f'Профиль "{profile_name}" успешно удалён!',
            callback=self.load_profiles
        )

    def show_create_profile(self, _instance) -> None:
        content = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(18))
        
        title_label = Label(
            text='СОЗДАНИЕ ПРОФИЛЯ',
            color=COLORS['YELLOW'],
            font_size=dp(22),
            bold=True,
            size_hint_y=None,
            height=dp(42),
            halign='center'
        )
        title_label.bind(size=title_label.setter('text_size'))
        content.add_widget(title_label)
        
        input_field = UIComponents.create_input_field('Введите имя профиля')
        content.add_widget(input_field)
        
        hint_label = Label(
            text='Имя профиля будет отображаться в заголовке приложения',
            color=COLORS['TEXT_HINT'],
            font_size=dp(14),
            size_hint_y=None,
            height=dp(45),
            halign='center',
            valign='middle',
            italic=True
        )
        hint_label.bind(size=hint_label.setter('text_size'))
        content.add_widget(hint_label)
        
        buttons = BoxLayout(spacing=dp(15), size_hint_y=None, height=dp(55))
        
        cancel_btn = UIComponents.create_secondary_button('ОТМЕНА', height=dp(50))
        ok_btn = UIComponents.create_primary_button('СОЗДАТЬ', height=dp(50))
        
        popup = Popup(
            title='',
            content=content,
            size_hint=(Dimensions.POPUP_WIDTH, 0.48),
            separator_height=0
        )
        
        # Фон попапа
        with popup.canvas.before:
            Color(*COLORS['CARD_BG'])
            popup.rect = Rectangle(pos=popup.pos, size=popup.size)
            popup.bind(pos=lambda inst, val: setattr(inst.rect, 'pos', val))
            popup.bind(size=lambda inst, val: setattr(inst.rect, 'size', val))
        
        def create(_instance):
            name = input_field.text.strip()
            if not name:
                popup.dismiss()
                self.show_popup('ОШИБКА', 'Имя профиля не может быть пустым')
                return
            
            profiles = self.data_manager.get_profiles()
            if name in profiles:
                popup.dismiss()
                self.show_popup('ОШИБКА', f'Профиль "{name}" уже существует')
                return
            
            profiles[name] = {
                "products": [],
                "stock": {},
                "orders": [],
                "daily_stats": {},
                "next_order_number": 1
            }
            self.data_manager.save_profiles(profiles)
            popup.dismiss()
            self.load_profiles()
            self.show_popup('УСПЕХ', f'Профиль "{name}" успешно создан!')
        
        cancel_btn.bind(on_press=popup.dismiss)
        ok_btn.bind(on_press=create)
        buttons.add_widget(cancel_btn)
        buttons.add_widget(ok_btn)
        content.add_widget(buttons)
        popup.open()


class ProfileScreen(BaseScreen):
    """Экран главного меню профиля."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title_label = None
        self.build_ui()

    def build_ui(self) -> None:
        layout = BoxLayout(orientation='vertical', padding=[Dimensions.PADDING, dp(8)], spacing=dp(10))
        
        # Заголовок с кнопкой назад
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=Dimensions.HEADER_HEIGHT, spacing=dp(10))
        back_btn = UIComponents.create_back_button('home', 'ВЫБОР ПРОФИЛЯ')
        header.add_widget(back_btn)
        
        self.title_label = Label(
            text='',
            size_hint_x=0.7,
            font_size=dp(20),
            bold=True,
            color=COLORS['YELLOW'],
            halign='left',
            valign='middle'
        )
        self.title_label.bind(size=self.title_label.setter('text_size'))
        header.add_widget(self.title_label)
        layout.add_widget(header)
        
        # Плитки меню
        grid = GridLayout(cols=2, spacing=dp(14), size_hint_y=None, padding=[dp(5), dp(10)])
        grid.bind(minimum_height=grid.setter('height'))
        
        tiles_config = [
            ("КАТАЛОГ ТОВАРОВ", "products"),
            ("ДОБАВИТЬ ТОВАР", "add_product"),
            ("СКЛАД", "warehouse"),
            ("СОЗДАТЬ ЗАКАЗ", "create_order"),
            ("АНАЛИЗ ПРОДАЖ", "sales_analysis"),
            ("ИСТОРИЯ ЗАКАЗОВ", "order_history"),
        ]
        
        for title, screen in tiles_config:
            btn = UIComponents.create_menu_tile(title, screen)
            grid.add_widget(btn)
        
        logout_btn = UIComponents.create_menu_tile("ВЫХОД ИЗ ПРОФИЛЯ", "home")
        logout_btn.background_color = COLORS['ACCENT_RED']
        logout_btn.color = COLORS['TEXT_PRIMARY']
        grid.add_widget(logout_btn)
        
        scroll_grid = ScrollView(size_hint_y=0.82)
        scroll_grid.add_widget(grid)
        layout.add_widget(scroll_grid)
        self.add_widget(layout)

    def on_enter(self) -> None:
        profile_name = self.get_current_profile()
        self.title_label.text = f'ПРОФИЛЬ: {profile_name}' if profile_name else 'ПРОФИЛЬ НЕ ВЫБРАН'


class ProductsScreen(BaseScreen):
    """Экран отображения каталога товаров."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scroll = None
        self.products_list = None
        self.build_ui()

    def build_ui(self) -> None:
        layout = BoxLayout(orientation='vertical', padding=Dimensions.PADDING, spacing=Dimensions.SPACING)
        layout.add_widget(UIComponents.create_back_button('profile', 'НАЗАД'))
        
        title = Label(
            text='КАТАЛОГ ТОВАРОВ',
            size_hint_y=None,
            height=Dimensions.TITLE_HEIGHT,
            font_size=dp(24),
            bold=True,
            color=COLORS['YELLOW'],
            halign='center',
            valign='middle'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)
        
        hint_label = Label(
            text='Нажмите "РЕДАКТИРОВАТЬ" для изменения характеристик товара',
            size_hint_y=None,
            height=dp(35),
            font_size=dp(15),
            color=COLORS['TEXT_HINT'],
            halign='center',
            valign='middle',
            italic=True
        )
        hint_label.bind(size=hint_label.setter('text_size'))
        layout.add_widget(hint_label)
        
        self.scroll = ScrollView(size_hint_y=0.75)
        self.products_list = GridLayout(cols=1, spacing=dp(12), size_hint_y=None, padding=[0, dp(5)])
        self.products_list.bind(minimum_height=self.products_list.setter('height'))
        self.scroll.add_widget(self.products_list)
        layout.add_widget(self.scroll)
        
        self.add_widget(layout)

    def on_enter(self) -> None:
        self.load_products()

    def load_products(self) -> None:
        self.products_list.clear_widgets()
        profile_data = self.get_profile_data()
        products = profile_data.get("products", [])
        
        if not products:
            empty_label = Label(
                text='НЕТ ТОВАРОВ В КАТАЛОГЕ',
                size_hint_y=None,
                height=dp(65),
                color=COLORS['TEXT_SECONDARY'],
                font_size=dp(21),
                bold=True,
                halign='center',
                valign='middle'
            )
            empty_label.bind(size=empty_label.setter('text_size'))
            self.products_list.add_widget(empty_label)
            
            hint_label = Label(
                text='Нажмите "ДОБАВИТЬ ТОВАР" в главном меню',
                size_hint_y=None,
                height=dp(40),
                color=COLORS['TEXT_HINT'],
                font_size=dp(16),
                halign='center',
                valign='middle',
                italic=True
            )
            hint_label.bind(size=hint_label.setter('text_size'))
            self.products_list.add_widget(hint_label)
            return
        
        for product in sorted(products, key=lambda x: x["name"]):
            card = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(100),
                padding=[dp(12), dp(8)],
                spacing=dp(12)
            )
            
            info_layout = BoxLayout(orientation='vertical', size_hint_x=0.82, spacing=dp(4))
            
            name_label = Label(
                text=f'НАЗВАНИЕ: {product["name"]}',
                font_size=dp(18),
                bold=True,
                color=COLORS['YELLOW'],
                size_hint_y=None,
                height=dp(30),
                halign='left',
                valign='middle'
            )
            name_label.bind(size=name_label.setter('text_size'))
            
            price_label = Label(
                text=f'ЦЕНА: {product["cost_price"]:.2f} ₽/кг',
                font_size=dp(16),
                color=COLORS['TEXT_PRIMARY'],
                size_hint_y=None,
                height=dp(28),
                halign='left',
                valign='middle'
            )
            price_label.bind(size=price_label.setter('text_size'))
            
            profit_label = Label(
                text=f'ПРИБЫЛЬ: {product["profit"]:.2f} ₽ ({product["percent_profit"]:.1f}%)',
                font_size=dp(16),
                color=COLORS['ACCENT_GREEN'],
                size_hint_y=None,
                height=dp(28),
                halign='left',
                valign='middle'
            )
            profit_label.bind(size=profit_label.setter('text_size'))
            
            info_layout.add_widget(name_label)
            info_layout.add_widget(price_label)
            info_layout.add_widget(profit_label)
            
            edit_btn = Button(
                text='РЕДАКТИРОВАТЬ',
                size_hint_x=0.18,
                size_hint_y=None,
                height=dp(84),
                background_normal='',
                background_color=COLORS['YELLOW'],
                color=COLORS['BACKGROUND'],
                font_size=dp(14),
                bold=True
            )
            edit_btn.bind(on_press=lambda instance, p=product: self.edit_product(p))
            
            # Добавляем границу к карточке
            with card.canvas.before:
                Color(*COLORS['CARD_BG'])
                card.rect = Rectangle(pos=card.pos, size=card.size)
            
            def update_rect(instance, value):
                instance.rect.pos = instance.pos
                instance.rect.size = instance.size
            
            card.bind(pos=update_rect, size=update_rect)
            
            card.add_widget(info_layout)
            card.add_widget(edit_btn)
            self.products_list.add_widget(card)

    def edit_product(self, product: Dict) -> None:
        app = App.get_running_app()
        app.product_to_edit = product
        self.manager.current = 'edit_product'


class AddProductScreen(BaseScreen):
    """Экран добавления нового товара в каталог."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name_input = None
        self.cost_input = None
        self.profit_input = None
        self.expenses_label = None
        self.percent_label = None
        self.build_ui()

    def build_ui(self) -> None:
        layout = BoxLayout(orientation='vertical', padding=Dimensions.PADDING, spacing=Dimensions.SPACING)
        layout.add_widget(UIComponents.create_back_button('profile', 'НАЗАД'))
        
        title = Label(
            text='ДОБАВЛЕНИЕ ТОВАРА',
            size_hint_y=None,
            height=Dimensions.TITLE_HEIGHT,
            font_size=dp(24),
            bold=True,
            color=COLORS['YELLOW'],
            halign='center',
            valign='middle'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)
        
        form_layout = GridLayout(cols=1, spacing=dp(16), size_hint_y=0.75)
        
        # Название
        form_layout.add_widget(Label(
            text='НАЗВАНИЕ ТОВАРА:',
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.name_input = UIComponents.create_input_field('Введите название товара')
        form_layout.add_widget(self.name_input)
        
        # Стоимость
        form_layout.add_widget(Label(
            text='СТОИМОСТЬ ЗА КГ (₽):',
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.cost_input = UIComponents.create_input_field('0.00')
        self.cost_input.bind(text=self.update_calculations)
        form_layout.add_widget(self.cost_input)
        
        # Прибыль
        form_layout.add_widget(Label(
            text='ПРИБЫЛЬ (₽):',
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.profit_input = UIComponents.create_input_field('0.00')
        self.profit_input.bind(text=self.update_calculations)
        form_layout.add_widget(self.profit_input)
        
        # Расчеты
        calc_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(110), spacing=dp(8))
        
        self.expenses_label = Label(
            text='ЗАТРАТЫ: 0.00 ₽',
            color=COLORS['ACCENT_AMBER'],
            font_size=dp(17),
            bold=True,
            size_hint_y=None,
            height=dp(35),
            halign='left'
        )
        self.expenses_label.bind(size=self.expenses_label.setter('text_size'))
        
        self.percent_label = Label(
            text='%ЗАТРАТ: 0.00% | %ПРИБЫЛИ: 0.00%',
            color=COLORS['YELLOW'],
            font_size=dp(16),
            bold=True,
            size_hint_y=None,
            height=dp(35),
            halign='left'
        )
        self.percent_label.bind(size=self.percent_label.setter('text_size'))
        
        formula_label = Label(
            text='Формула: %Затрат = (Затраты / (Затраты + Прибыль)) × 100%',
            color=COLORS['TEXT_HINT'],
            font_size=dp(14),
            italic=True,
            size_hint_y=None,
            height=dp(30),
            halign='left'
        )
        formula_label.bind(size=formula_label.setter('text_size'))
        
        calc_layout.add_widget(self.expenses_label)
        calc_layout.add_widget(self.percent_label)
        calc_layout.add_widget(formula_label)
        form_layout.add_widget(calc_layout)
        
        layout.add_widget(form_layout)
        
        save_btn = UIComponents.create_primary_button('СОХРАНИТЬ ТОВАР', height=dp(60))
        save_btn.bind(on_press=self.save_product)
        layout.add_widget(save_btn)
        
        self.add_widget(layout)

    def on_enter(self) -> None:
        self.name_input.text = ''
        self.cost_input.text = '0.00'
        self.profit_input.text = '0.00'
        self.expenses_label.text = 'ЗАТРАТЫ: 0.00 ₽'
        self.percent_label.text = '%ЗАТРАТ: 0.00% | %ПРИБЫЛИ: 0.00%'

    def update_calculations(self, _instance, _value) -> None:
        try:
            cost = float(self.cost_input.text or '0')
            profit = float(self.profit_input.text or '0')
            if cost > 0 and 0 <= profit <= cost:
                expenses = cost - profit
                percent_exp = self.business_logic.calculate_percent_expenses(cost, profit)
                percent_profit = self.business_logic.calculate_percent_profit(cost, profit)
                self.expenses_label.text = f'ЗАТРАТЫ: {expenses:.2f} ₽'
                self.percent_label.text = f'%ЗАТРАТ: {percent_exp:.2f}% | %ПРИБЫЛИ: {percent_profit:.2f}%'
        except ValueError:
            pass

    def save_product(self, _instance) -> None:
        profile_data = self.get_profile_data()
        
        name, error = Validators.validate_non_empty(self.name_input.text, "Название товара")
        if error:
            self.show_popup('ОШИБКА', error)
            return
        
        cost, error = Validators.validate_positive_float(self.cost_input.text, "Стоимость")
        if error:
            self.show_popup('ОШИБКА', error)
            return
        
        profit, error = Validators.validate_positive_float(self.profit_input.text or '0', "Прибыль")
        if error:
            self.show_popup('ОШИБКА', error)
            return
        
        if profit > cost:
            self.show_popup('ОШИБКА', 'Прибыль не может превышать стоимость')
            return
        
        existing = [p["name"].lower() for p in profile_data.get("products", [])]
        if name.lower() in existing:
            self.show_popup('ОШИБКА', f'Товар "{name}" уже существует')
            return
        
        expenses = cost - profit
        percent_exp = self.business_logic.calculate_percent_expenses(cost, profit)
        percent_profit = self.business_logic.calculate_percent_profit(cost, profit)
        
        product = {
            "name": name,
            "cost_price": cost,
            "profit": profit,
            "expenses": expenses,
            "percent_expenses": percent_exp,
            "percent_profit": percent_profit
        }
        
        profile_data["products"].append(product)
        
        if name not in profile_data["stock"]:
            profile_data["stock"][name] = {
                "current_quantity": 0.0,
                "total_value": 0.0,
                "history": []
            }
        
        self.save_profile_data(profile_data)
        
        self.show_popup('УСПЕХ', f'Товар "{name}" успешно добавлен!',
                       callback=lambda: setattr(self.manager, 'current', 'profile'))


class EditProductScreen(BaseScreen):
    """Экран редактирования товара."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title_label = None
        self.name_input = None
        self.cost_input = None
        self.profit_input = None
        self.expenses_label = None
        self.percent_label = None
        self.build_ui()

    def build_ui(self) -> None:
        layout = BoxLayout(orientation='vertical', padding=Dimensions.PADDING, spacing=Dimensions.SPACING)
        layout.add_widget(UIComponents.create_back_button('products', 'НАЗАД'))
        
        self.title_label = Label(
            text='РЕДАКТИРОВАНИЕ ТОВАРА',
            size_hint_y=None,
            height=Dimensions.TITLE_HEIGHT,
            font_size=dp(24),
            bold=True,
            color=COLORS['YELLOW'],
            halign='center',
            valign='middle'
        )
        self.title_label.bind(size=self.title_label.setter('text_size'))
        layout.add_widget(self.title_label)
        
        form_layout = GridLayout(cols=1, spacing=dp(16), size_hint_y=0.7)
        
        form_layout.add_widget(Label(
            text='НАЗВАНИЕ ТОВАРА:',
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.name_input = UIComponents.create_input_field()
        form_layout.add_widget(self.name_input)
        
        form_layout.add_widget(Label(
            text='СТОИМОСТЬ ЗА КГ (₽):',
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.cost_input = UIComponents.create_input_field('0.00')
        self.cost_input.bind(text=self.update_calculations)
        form_layout.add_widget(self.cost_input)
        
        form_layout.add_widget(Label(
            text='ПРИБЫЛЬ (₽):',
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.profit_input = UIComponents.create_input_field('0.00')
        self.profit_input.bind(text=self.update_calculations)
        form_layout.add_widget(self.profit_input)
        
        calc_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(110), spacing=dp(8))
        
        self.expenses_label = Label(
            text='ЗАТРАТЫ: 0.00 ₽',
            color=COLORS['ACCENT_AMBER'],
            font_size=dp(17),
            bold=True,
            size_hint_y=None,
            height=dp(35),
            halign='left'
        )
        self.expenses_label.bind(size=self.expenses_label.setter('text_size'))
        
        self.percent_label = Label(
            text='%ЗАТРАТ: 0.00% | %ПРИБЫЛИ: 0.00%',
            color=COLORS['YELLOW'],
            font_size=dp(16),
            bold=True,
            size_hint_y=None,
            height=dp(35),
            halign='left'
        )
        self.percent_label.bind(size=self.percent_label.setter('text_size'))
        
        formula_label = Label(
            text='Формула: %Затрат = (Затраты / (Затраты + Прибыль)) × 100%',
            color=COLORS['TEXT_HINT'],
            font_size=dp(14),
            italic=True,
            size_hint_y=None,
            height=dp(30),
            halign='left'
        )
        formula_label.bind(size=formula_label.setter('text_size'))
        
        calc_layout.add_widget(self.expenses_label)
        calc_layout.add_widget(self.percent_label)
        calc_layout.add_widget(formula_label)
        form_layout.add_widget(calc_layout)
        
        layout.add_widget(form_layout)
        
        btn_layout = BoxLayout(spacing=dp(16), size_hint_y=None, height=dp(65))
        
        delete_btn = UIComponents.create_secondary_button('УДАЛИТЬ', height=dp(60), color=COLORS['ACCENT_RED'])
        save_btn = UIComponents.create_primary_button('СОХРАНИТЬ', height=dp(60))
        
        delete_btn.bind(on_press=self.confirm_delete)
        save_btn.bind(on_press=self.save_product)
        
        btn_layout.add_widget(delete_btn)
        btn_layout.add_widget(save_btn)
        layout.add_widget(btn_layout)
        
        self.add_widget(layout)

    def on_enter(self) -> None:
        app = App.get_running_app()
        product = app.product_to_edit
        self.title_label.text = f'РЕДАКТИРОВАНИЕ: {product["name"]}'
        self.name_input.text = product["name"]
        self.cost_input.text = f'{product["cost_price"]:.2f}'
        self.profit_input.text = f'{product["profit"]:.2f}'
        self.update_calculations(None, None)

    def update_calculations(self, _instance, _value) -> None:
        try:
            cost = float(self.cost_input.text or '0')
            profit = float(self.profit_input.text or '0')
            if cost > 0 and 0 <= profit <= cost:
                expenses = cost - profit
                percent_exp = self.business_logic.calculate_percent_expenses(cost, profit)
                percent_profit = self.business_logic.calculate_percent_profit(cost, profit)
                self.expenses_label.text = f'ЗАТРАТЫ: {expenses:.2f} ₽'
                self.percent_label.text = f'%ЗАТРАТ: {percent_exp:.2f}% | %ПРИБЫЛИ: {percent_profit:.2f}%'
        except ValueError:
            pass

    def confirm_delete(self, _instance) -> None:
        product_name = self.name_input.text.strip()
        self.show_confirmation(
            title='УДАЛЕНИЕ ТОВАРА',
            message=f'Вы уверены, что хотите удалить товар "{product_name}"?\n'
                    f'Все данные о товаре будут удалены!',
            yes_callback=self.delete_product
        )

    def delete_product(self) -> None:
        app = App.get_running_app()
        profile_data = self.get_profile_data()
        product_name = self.name_input.text.strip()
        
        profile_data["products"] = [
            p for p in profile_data["products"] if p["name"] != product_name
        ]
        
        if product_name in profile_data["stock"]:
            del profile_data["stock"][product_name]
        
        for order in profile_data.get("orders", []):
            for item in order["items"]:
                if item["product"] == product_name:
                    item["product"] = "УДАЛЕННЫЙ ТОВАР"
        
        self.save_profile_data(profile_data)
        
        self.show_popup(
            'УСПЕХ',
            f'Товар "{product_name}" удален!',
            callback=lambda: setattr(self.manager, 'current', 'products')
        )

    def save_product(self, _instance) -> None:
        app = App.get_running_app()
        profile_data = self.get_profile_data()
        old_name = app.product_to_edit["name"]
        
        new_name, error = Validators.validate_non_empty(self.name_input.text, "Название товара")
        if error:
            self.show_popup('ОШИБКА', error)
            return
        
        cost, error = Validators.validate_positive_float(self.cost_input.text, "Стоимость")
        if error:
            self.show_popup('ОШИБКА', error)
            return
        
        profit, error = Validators.validate_positive_float(self.profit_input.text or '0', "Прибыль")
        if error:
            self.show_popup('ОШИБКА', error)
            return
        
        if profit > cost:
            self.show_popup('ОШИБКА', 'Прибыль не может превышать стоимость')
            return
        
        existing = [p["name"].lower() for p in profile_data.get("products", [])
                    if p["name"].lower() != old_name.lower()]
        if new_name.lower() in existing:
            self.show_popup('ОШИБКА', f'Товар "{new_name}" уже существует')
            return
        
        expenses = cost - profit
        percent_exp = self.business_logic.calculate_percent_expenses(cost, profit)
        percent_profit = self.business_logic.calculate_percent_profit(cost, profit)
        
        for product in profile_data["products"]:
            if product["name"] == old_name:
                product["name"] = new_name
                product["cost_price"] = cost
                product["profit"] = profit
                product["expenses"] = expenses
                product["percent_expenses"] = percent_exp
                product["percent_profit"] = percent_profit
                break
        
        if old_name != new_name:
            if old_name in profile_data["stock"]:
                profile_data["stock"][new_name] = profile_data["stock"].pop(old_name)
            
            for order in profile_data.get("orders", []):
                for item in order["items"]:
                    if item["product"] == old_name:
                        item["product"] = new_name
        
        self.save_profile_data(profile_data)
        
        self.show_popup(
            'УСПЕХ',
            f'Товар "{new_name}" успешно обновлен!',
            callback=lambda: setattr(self.manager, 'current', 'products')
        )


class WarehouseScreen(BaseScreen):
    """Экран управления складом."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stats_label = None
        self.warehouse_list = None
        self.build_ui()

    def build_ui(self) -> None:
        layout = BoxLayout(orientation='vertical', padding=Dimensions.PADDING, spacing=dp(10))
        layout.add_widget(UIComponents.create_back_button('profile', 'НАЗАД'))
        
        self.stats_label = Label(
            text='ОБЩАЯ СТОИМОСТЬ: 0.00 ₽\nОБЩИЙ ОСТАТОК: 0.00 кг',
            size_hint_y=None,
            height=dp(80),
            font_size=dp(17),
            halign='center',
            valign='middle',
            color=COLORS['YELLOW'],
            bold=True
        )
        self.stats_label.bind(size=self.stats_label.setter('text_size'))
        layout.add_widget(self.stats_label)
        
        scroll = ScrollView(size_hint_y=0.62)
        self.warehouse_list = GridLayout(cols=1, spacing=dp(12), size_hint_y=None, padding=[0, dp(5)])
        self.warehouse_list.bind(minimum_height=self.warehouse_list.setter('height'))
        scroll.add_widget(self.warehouse_list)
        layout.add_widget(scroll)
        
        btn_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(58), spacing=dp(10))
        
        add_btn = UIComponents.create_secondary_button('ПОПОЛНИТЬ', height=dp(55), color=COLORS['ACCENT_GREEN'])
        edit_btn = UIComponents.create_secondary_button('СКОРРЕКТИРОВАТЬ', height=dp(55), color=COLORS['ACCENT_AMBER'])
        history_btn = UIComponents.create_secondary_button('ИСТОРИЯ', height=dp(55), color=COLORS['ACCENT_RED'])
        
        add_btn.bind(on_press=self.go_to_add_stock)
        edit_btn.bind(on_press=self.open_edit_warehouse_dialog)
        history_btn.bind(on_press=self.go_to_stock_history)
        
        btn_layout.add_widget(add_btn)
        btn_layout.add_widget(edit_btn)
        btn_layout.add_widget(history_btn)
        layout.add_widget(btn_layout)
        
        self.add_widget(layout)

    def on_enter(self) -> None:
        self.load_warehouse()

    def load_warehouse(self) -> None:
        profile_data = self.get_profile_data()
        
        total_value = sum(data["total_value"] for data in profile_data["stock"].values())
        total_qty = sum(data["current_quantity"] for data in profile_data["stock"].values())
        total_products = len(profile_data.get("products", []))
        products_with_stock = sum(1 for data in profile_data["stock"].values() if data["current_quantity"] > 0)
        
        self.stats_label.text = (
            f'ВСЕГО ТОВАРОВ: {total_products}\n'
            f'С ОСТАТКОМ: {products_with_stock}\n'
            f'ОБЩИЙ ОСТАТОК: {total_qty:.2f} кг\n'
            f'ОБЩАЯ СТОИМОСТЬ: {total_value:.2f} ₽'
        )
        
        self.warehouse_list.clear_widgets()
        products = profile_data.get("products", [])
        
        if not products:
            empty_label = Label(
                text='НЕТ ТОВАРОВ В КАТАЛОГЕ',
                size_hint_y=None,
                height=dp(60),
                color=COLORS['TEXT_SECONDARY'],
                font_size=dp(21),
                bold=True,
                halign='center',
                valign='middle'
            )
            empty_label.bind(size=empty_label.setter('text_size'))
            self.warehouse_list.add_widget(empty_label)
            return
        
        for product in sorted(products, key=lambda x: x["name"]):
            product_name = product["name"]
            stock_data = profile_data["stock"].get(product_name, {
                "current_quantity": 0.0,
                "total_value": 0.0,
                "history": []
            })
            
            qty = stock_data["current_quantity"]
            total_value = stock_data["total_value"]
            avg_price = total_value / qty if qty > 0 else 0.0
            
            card = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(95),
                padding=[dp(12), dp(8)],
                spacing=dp(12)
            )
            
            info_layout = BoxLayout(orientation='vertical', size_hint_x=0.82, spacing=dp(3))
            
            name_label = Label(
                text=product_name.upper(),
                font_size=dp(17),
                bold=True,
                color=COLORS['YELLOW'],
                size_hint_y=None,
                height=dp(28),
                halign='left',
                valign='middle'
            )
            name_label.bind(size=name_label.setter('text_size'))
            
            qty_label = Label(
                text=f'ОСТАТОК: {qty:.2f} кг',
                font_size=dp(16),
                color=COLORS['ACCENT_GREEN'] if qty > 0 else COLORS['ACCENT_RED'],
                size_hint_y=None,
                height=dp(28),
                halign='left',
                valign='middle'
            )
            qty_label.bind(size=qty_label.setter('text_size'))
            
            price_label = Label(
                text=f'СР. ЦЕНА: {avg_price:.2f} ₽/кг',
                font_size=dp(16),
                color=COLORS['TEXT_PRIMARY'],
                size_hint_y=None,
                height=dp(28),
                halign='left',
                valign='middle'
            )
            price_label.bind(size=price_label.setter('text_size'))
            
            info_layout.add_widget(name_label)
            info_layout.add_widget(qty_label)
            info_layout.add_widget(price_label)
            
            edit_btn = Button(
                text='ИЗМЕНИТЬ',
                size_hint_x=0.18,
                size_hint_y=None,
                height=dp(79),
                background_normal='',
                background_color=COLORS['YELLOW'],
                color=COLORS['BACKGROUND'],
                font_size=dp(14),
                bold=True
            )
            edit_btn.bind(on_press=lambda instance, p=product_name: self.edit_warehouse_item(p))
            
            # Фон карточки
            with card.canvas.before:
                Color(*COLORS['CARD_BG'])
                card.rect = Rectangle(pos=card.pos, size=card.size)
            
            def update_rect(instance, value):
                instance.rect.pos = instance.pos
                instance.rect.size = instance.size
            
            card.bind(pos=update_rect, size=update_rect)
            
            card.add_widget(info_layout)
            card.add_widget(edit_btn)
            self.warehouse_list.add_widget(card)

    def go_to_add_stock(self, _instance) -> None:
        self.manager.current = 'add_stock'

    def open_edit_warehouse_dialog(self, _instance) -> None:
        self.edit_warehouse_item(None)

    def go_to_stock_history(self, _instance) -> None:
        self.manager.current = 'stock_history'

    def edit_warehouse_item(self, product_name: Optional[str]) -> None:
        profile_data = self.get_profile_data()
        
        if product_name is None:
            if not profile_data.get("products"):
                self.show_popup('ОШИБКА', 'Нет товаров в каталоге')
                return
            
            content = BoxLayout(orientation='vertical', padding=dp(18), spacing=dp(12))
            title_label = Label(
                text='ВЫБЕРИТЕ ТОВАР ДЛЯ КОРРЕКТИРОВКИ',
                color=COLORS['YELLOW'],
                font_size=dp(19),
                bold=True,
                size_hint_y=None,
                height=dp(42),
                halign='center'
            )
            content.add_widget(title_label)
            
            scroll = ScrollView(size_hint_y=0.72)
            products_list = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
            products_list.bind(minimum_height=products_list.setter('height'))
            
            for product in sorted(profile_data["products"], key=lambda x: x["name"]):
                btn = Button(
                    text=product["name"].upper(),
                    size_hint_y=None,
                    height=dp(50),
                    background_normal='',
                    background_color=COLORS['CARD_BG'],
                    color=COLORS['YELLOW'],
                    font_size=dp(17),
                    bold=True
                )
                btn.bind(on_press=lambda btn, p=product["name"]: self._open_edit_dialog(p, content.parent))
                products_list.add_widget(btn)
            
            scroll.add_widget(products_list)
            content.add_widget(scroll)
            
            popup = Popup(
                title='',
                content=content,
                size_hint=(Dimensions.POPUP_WIDTH, 0.82),
                separator_height=0
            )
            
            with popup.canvas.before:
                Color(*COLORS['CARD_BG'])
                popup.rect = Rectangle(pos=popup.pos, size=popup.size)
                popup.bind(pos=lambda inst, val: setattr(inst.rect, 'pos', val))
                popup.bind(size=lambda inst, val: setattr(inst.rect, 'size', val))
            
            popup.open()
            return
        
        if product_name not in profile_data["stock"]:
            profile_data["stock"][product_name] = {
                "current_quantity": 0.0,
                "total_value": 0.0,
                "history": []
            }
            self.save_profile_data(profile_data)
        
        stock_data = profile_data["stock"][product_name]
        current_qty = stock_data["current_quantity"]
        current_value = stock_data["total_value"]
        avg_price = current_value / current_qty if current_qty > 0 else 0.0
        
        content = BoxLayout(orientation='vertical', padding=dp(18), spacing=dp(16))
        title_label = Label(
            text=f'РЕДАКТИРОВАНИЕ: {product_name.upper()}',
            color=COLORS['YELLOW'],
            font_size=dp(19),
            bold=True,
            size_hint_y=None,
            height=dp(42),
            halign='center'
        )
        content.add_widget(title_label)
        
        product_info = next((p for p in profile_data["products"] if p["name"] == product_name), None)
        if product_info:
            percent_exp = self.business_logic.calculate_percent_expenses(
                product_info['cost_price'], product_info['profit'] 
            )
            percent_profit = self.business_logic.calculate_percent_profit(
                product_info['cost_price'], product_info['profit']
            )
            
            price_info = Label(
                text=f"ЦЕНА ПРОДАЖИ: {product_info['cost_price']:.2f} ₽/кг\n"
                     f"ПРИБЫЛЬ: {product_info['profit']:.2f} ₽ ({percent_profit:.1f}%)",
                color=COLORS['TEXT_HINT'],
                font_size=dp(15),
                size_hint_y=None,
                height=dp(65),
                halign='center',
                valign='middle'
            )
            content.add_widget(price_info)
        
        qty_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(85))
        qty_layout.add_widget(Label(
            text='ОСТАТОК (кг):',
            color=COLORS['YELLOW'],
            font_size=dp(17),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.qty_input = UIComponents.create_input_field(text=f'{current_qty:.2f}')
        qty_layout.add_widget(self.qty_input)
        content.add_widget(qty_layout)
        
        price_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(85))
        price_layout.add_widget(Label(
            text='СРЕДНЯЯ ЦЕНА ЗАКУПКИ (₽/кг):',
            color=COLORS['YELLOW'],
            font_size=dp(17),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.price_input = UIComponents.create_input_field(text=f'{avg_price:.2f}')
        price_layout.add_widget(self.price_input)
        content.add_widget(price_layout)
        
        calc_label = Label(
            text=f'ТЕКУЩАЯ СТОИМОСТЬ ОСТАТКА: {current_value:.2f} ₽',
            color=COLORS['TEXT_HINT'],
            font_size=dp(15),
            size_hint_y=None,
            height=dp(38),
            halign='center',
            valign='middle'
        )
        content.add_widget(calc_label)
        
        buttons_layout = BoxLayout(spacing=dp(16), size_hint_y=None, height=dp(65))
        
        cancel_btn = UIComponents.create_secondary_button('ОТМЕНА', height=dp(60), color=COLORS['ACCENT_RED'])
        save_btn = UIComponents.create_primary_button('СОХРАНИТЬ', height=dp(60))
        
        popup = Popup(
            title='',
            content=content,
            size_hint=(Dimensions.POPUP_WIDTH, 0.85),
            separator_height=0
        )
        
        with popup.canvas.before:
            Color(*COLORS['CARD_BG'])
            popup.rect = Rectangle(pos=popup.pos, size=popup.size)
            popup.bind(pos=lambda inst, val: setattr(inst.rect, 'pos', val))
            popup.bind(size=lambda inst, val: setattr(inst.rect, 'size', val))
        
        def cancel(_instance):
            popup.dismiss()
        
        def save(_instance):
            try:
                new_quantity = float(self.qty_input.text.replace(',', '.'))
                new_avg_price = float(self.price_input.text.replace(',', '.'))
                
                if new_quantity < 0:
                    self.show_popup('ОШИБКА', 'Остаток не может быть отрицательным!')
                    return
                
                if new_avg_price < 0:
                    self.show_popup('ОШИБКА', 'Цена закупки не может быть отрицательной!')
                    return
                
                old_quantity = stock_data["current_quantity"]
                old_total_value = stock_data["total_value"]
                
                stock_data["current_quantity"] = new_quantity
                stock_data["total_value"] = new_quantity * new_avg_price
                
                operation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                stock_data["history"].append({
                    "date": operation_time,
                    "quantity": new_quantity - old_quantity,
                    "price_per_kg": new_avg_price,
                    "operation": "корректировка",
                    "total_amount": new_quantity * new_avg_price,
                    "balance_after": new_quantity
                })
                
                self.save_profile_data(profile_data)
                popup.dismiss()
                self.load_warehouse()
                self.show_popup('УСПЕХ', f'Товар "{product_name}" успешно скорректирован!')
            
            except ValueError:
                self.show_popup('ОШИБКА', 'Введите корректные числовые значения!')
        
        cancel_btn.bind(on_press=cancel)
        save_btn.bind(on_press=save)
        
        buttons_layout.add_widget(cancel_btn)
        buttons_layout.add_widget(save_btn)
        content.add_widget(buttons_layout)
        popup.open()

    def _open_edit_dialog(self, product_name: str, popup: Popup) -> None:
        popup.dismiss()
        self.edit_warehouse_item(product_name)


class AddStockScreen(BaseScreen):
    """Экран добавления товара на склад."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.product_btn = None
        self.qty_input = None
        self.price_input = None
        self.build_ui()

    def build_ui(self) -> None:
        layout = BoxLayout(orientation='vertical', padding=Dimensions.PADDING, spacing=Dimensions.SPACING)
        layout.add_widget(UIComponents.create_back_button('warehouse', 'НАЗАД К СКЛАДУ'))
        
        title = Label(
            text='ПОПОЛНЕНИЕ СКЛАДА',
            size_hint_y=None,
            height=Dimensions.TITLE_HEIGHT,
            font_size=dp(24),
            bold=True,
            color=COLORS['YELLOW'],
            halign='center',
            valign='middle'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)
        
        form_layout = GridLayout(cols=1, spacing=dp(15), size_hint_y=0.72)
        
        form_layout.add_widget(Label(
            text='ТОВАР:',
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.product_btn = Button(
            text='ВЫБЕРИТЕ ТОВАР',
            size_hint_y=None,
            height=Dimensions.INPUT_HEIGHT,
            background_normal='',
            background_color=COLORS['CARD_BG'],
            color=COLORS['TEXT_HINT'],
            font_size=dp(18),
            bold=True,
            halign='left',
            valign='middle'
        )
        self.product_btn.bind(size=self.product_btn.setter('text_size'))
        self.product_btn.bind(on_press=self.show_product_dropdown)
        
        # Добавляем границу
        with self.product_btn.canvas.after:
            Color(*COLORS['BORDER'])
            self.product_btn.border = Line(rectangle=(self.product_btn.x, self.product_btn.y, self.product_btn.width, self.product_btn.height), width=1.5)
        
        def update_border(instance, value):
            instance.border.rectangle = (instance.x, instance.y, instance.width, instance.height)
        
        self.product_btn.bind(pos=update_border, size=update_border)
        
        form_layout.add_widget(self.product_btn)
        
        form_layout.add_widget(Label(
            text='КОЛИЧЕСТВО (кг):',
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.qty_input = UIComponents.create_input_field('1.0')
        form_layout.add_widget(self.qty_input)
        
        form_layout.add_widget(Label(
            text='ЦЕНА ЗАКУПКИ ЗА КГ (₽):',
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.price_input = UIComponents.create_input_field('100.00')
        form_layout.add_widget(self.price_input)
        
        info_label = Label(
            text='Цена закупки используется для расчёта стоимости запасов',
            color=COLORS['TEXT_HINT'],
            font_size=dp(15),
            italic=True,
            size_hint_y=None,
            height=dp(40),
            halign='center',
            valign='middle'
        )
        info_label.bind(size=info_label.setter('text_size'))
        form_layout.add_widget(info_label)
        
        layout.add_widget(form_layout)
        
        save_btn = UIComponents.create_primary_button('ДОБАВИТЬ НА СКЛАД', height=dp(62))
        save_btn.bind(on_press=self.save_to_stock)
        layout.add_widget(save_btn)
        
        self.add_widget(layout)

    def on_enter(self) -> None:
        self.product_btn.text = 'ВЫБЕРИТЕ ТОВАР'
        self.qty_input.text = '1.0'
        self.price_input.text = '100.00'
        self.product_btn.color = COLORS['TEXT_HINT']

    def show_product_dropdown(self, _instance) -> None:
        profile_data = self.get_profile_data()
        products = [p["name"] for p in profile_data.get("products", [])]
        
        if not products:
            self.show_popup('ОШИБКА', 'Нет товаров в каталоге')
            return
        
        dropdown = DropDown()
        for product in products:
            btn = Button(
                text=product.upper(),
                size_hint_y=None,
                height=dp(48),
                background_normal='',
                background_color=COLORS['CARD_BG'],
                color=COLORS['YELLOW'],
                font_size=dp(17),
                bold=True
            )
            btn.bind(on_release=lambda btn, p=product: self.select_product(p, dropdown))
            dropdown.add_widget(btn)
        
        dropdown.open(self.product_btn)

    def select_product(self, product_name: str, dropdown: DropDown) -> None:
        self.product_btn.text = product_name.upper()
        self.product_btn.color = COLORS['YELLOW']
        dropdown.dismiss()

    def save_to_stock(self, _instance) -> None:
        product_name = self.product_btn.text
        if product_name == 'ВЫБЕРИТЕ ТОВАР':
            self.show_popup('ОШИБКА', 'Выберите товар!')
            return
        
        qty, error = Validators.validate_positive_float(self.qty_input.text, "Количество")
        if error:
            self.show_popup('ОШИБКА', error)
            return
        
        price, error = Validators.validate_positive_float(self.price_input.text, "Цена закупки")
        if error:
            self.show_popup('ОШИБКА', error)
            return
        
        profile_data = self.get_profile_data()
        
        if product_name not in profile_data["stock"]:
            profile_data["stock"][product_name] = {
                "current_quantity": 0.0,
                "total_value": 0.0,
                "history": []
            }
        
        stock_data = profile_data["stock"][product_name]
        previous_quantity = stock_data["current_quantity"]
        previous_value = stock_data["total_value"]
        
        stock_data["current_quantity"] += qty
        stock_data["total_value"] += qty * price
        
        operation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stock_data["history"].append({
            "date": operation_time,
            "quantity": qty,
            "price_per_kg": price,
            "operation": "пополнение",
            "total_amount": qty * price,
            "balance_after": stock_data["current_quantity"]
        })
        
        self.save_profile_data(profile_data)
        
        self.show_popup(
            'УСПЕХ',
            f'На склад добавлено {qty:.2f} кг товара "{product_name}"\n'
            f'Цена закупки: {price:.2f} ₽/кг',
            callback=lambda: setattr(self.manager, 'current', 'warehouse')
        )


class CreateOrderScreen(BaseScreen):
    """Экран создания нового заказа."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.order_items: List[Dict] = []
        self.delivery_enabled: bool = True
        self.current_order_number: int = 1
        self.title_label = None
        self.product_btn = None
        self.qty_input = None
        self.info_label = None
        self.delivery_btn = None
        self.items_scroll = None
        self.items_list = None
        self.total_label = None
        self.build_ui()

    def build_ui(self) -> None:
        layout = BoxLayout(orientation='vertical', padding=Dimensions.PADDING, spacing=dp(10))
        layout.add_widget(UIComponents.create_back_button('profile', 'НАЗАД'))
        
        self.title_label = Label(
            text='ЗАКАЗ №1',
            size_hint_y=None,
            height=dp(50),
            font_size=dp(24),
            bold=True,
            color=COLORS['YELLOW'],
            halign='center',
            valign='middle'
        )
        self.title_label.bind(size=self.title_label.setter('text_size'))
        layout.add_widget(self.title_label)
        
        # Выбор товара
        product_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(105))
        product_layout.add_widget(Label(
            text='ТОВАР:',
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.product_btn = Button(
            text='ВЫБЕРИТЕ ТОВАР',
            size_hint_y=None,
            height=Dimensions.INPUT_HEIGHT,
            background_normal='',
            background_color=COLORS['CARD_BG'],
            color=COLORS['TEXT_HINT'],
            font_size=dp(18),
            bold=True,
            halign='left',
            valign='middle'
        )
        self.product_btn.bind(size=self.product_btn.setter('text_size'))
        self.product_btn.bind(on_press=self.show_product_dropdown)
        
        # Добавляем границу
        with self.product_btn.canvas.after:
            Color(*COLORS['BORDER'])
            self.product_btn.border = Line(rectangle=(self.product_btn.x, self.product_btn.y, self.product_btn.width, self.product_btn.height), width=1.5)
        
        def update_border(instance, value):
            instance.border.rectangle = (instance.x, instance.y, instance.width, instance.height)
        
        self.product_btn.bind(pos=update_border, size=update_border)
        
        product_layout.add_widget(self.product_btn)
        layout.add_widget(product_layout)
        
        # Количество
        qty_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(95))
        qty_layout.add_widget(Label(
            text='КОЛИЧЕСТВО (кг):',
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.qty_input = UIComponents.create_input_field('1.0')
        qty_layout.add_widget(self.qty_input)
        layout.add_widget(qty_layout)
        
        # Информация о товаре
        self.info_label = Label(
            text='',
            size_hint_y=None,
            height=dp(65),
            font_size=dp(15),
            halign='left',
            valign='middle',
            color=COLORS['TEXT_HINT']
        )
        self.info_label.bind(size=self.info_label.setter('text_size'))
        layout.add_widget(self.info_label)
        
        # Доставка
        delivery_layout = BoxLayout(size_hint_y=None, height=Dimensions.BTN_HEIGHT)
        self.delivery_btn = Button(
            text='ДОСТАВКА: ВКЛ',
            background_normal='',
            background_color=COLORS['YELLOW'],
            color=COLORS['BACKGROUND'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=Dimensions.BTN_HEIGHT
        )
        self.delivery_btn.bind(on_press=self.toggle_delivery)
        delivery_layout.add_widget(self.delivery_btn)
        layout.add_widget(delivery_layout)
        
        # Позиции заказа
        items_layout = BoxLayout(orientation='vertical', size_hint_y=0.32)
        items_layout.add_widget(Label(
            text='ПОЗИЦИИ ЗАКАЗА:',
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.items_scroll = ScrollView(size_hint_y=0.82)
        self.items_list = GridLayout(cols=1, spacing=dp(6), size_hint_y=None, padding=[0, dp(5)])
        self.items_list.bind(minimum_height=self.items_list.setter('height'))
        self.items_scroll.add_widget(self.items_list)
        items_layout.add_widget(self.items_scroll)
        layout.add_widget(items_layout)
        
        # Итого и кнопки
        total_layout = BoxLayout(orientation='vertical', size_hint_y=0.18)
        self.total_label = Label(
            text='ИТОГО: 0.00 ₽',
            font_size=dp(22),
            bold=True,
            color=COLORS['YELLOW'],
            size_hint_y=0.45,
            halign='center',
            valign='middle'
        )
        self.total_label.bind(size=self.total_label.setter('text_size'))
        total_layout.add_widget(self.total_label)
        
        buttons_layout = BoxLayout(spacing=dp(14), size_hint_y=0.55)
        
        add_btn = UIComponents.create_secondary_button('ДОБАВИТЬ', height=dp(52))
        save_btn = UIComponents.create_primary_button('СОХРАНИТЬ', height=dp(52))
        
        add_btn.bind(on_press=self.add_item)
        save_btn.bind(on_press=self.save_order)
        
        buttons_layout.add_widget(add_btn)
        buttons_layout.add_widget(save_btn)
        total_layout.add_widget(buttons_layout)
        layout.add_widget(total_layout)
        
        self.add_widget(layout)

    def on_enter(self) -> None:
        profile_data = self.get_profile_data()
        self.current_order_number = profile_data.get("next_order_number", 1)
        self.title_label.text = f'ЗАКАЗ №{self.current_order_number}'
        self.order_items = []
        self.items_list.clear_widgets()
        self.product_btn.text = 'ВЫБЕРИТЕ ТОВАР'
        self.product_btn.color = COLORS['TEXT_HINT']
        self.qty_input.text = '1.0'
        self.total_label.text = 'ИТОГО: 0.00 ₽'
        self.info_label.text = ''

    def show_product_dropdown(self, _instance) -> None:
        profile_data = self.get_profile_data()
        products = [
            p["name"] for p in profile_data.get("products", [])
            if profile_data["stock"].get(p["name"], {"current_quantity": 0})["current_quantity"] > 0
        ]
        
        if not products:
            self.show_popup('ОШИБКА', 'Нет товаров с остатком на складе')
            return
        
        dropdown = DropDown()
        for product in products:
            btn = Button(
                text=product.upper(),
                size_hint_y=None,
                height=dp(48),
                background_normal='',
                background_color=COLORS['CARD_BG'],
                color=COLORS['YELLOW'],
                font_size=dp(17),
                bold=True
            )
            btn.bind(on_release=lambda btn, p=product: self.select_product(p, dropdown))
            dropdown.add_widget(btn)
        
        dropdown.open(self.product_btn)

    def select_product(self, product_name: str, dropdown: DropDown) -> None:
        self.product_btn.text = product_name.upper()
        self.product_btn.color = COLORS['YELLOW']
        dropdown.dismiss()
        
        profile_data = self.get_profile_data()
        product = next((p for p in profile_data["products"] if p["name"] == product_name), None)
        stock_data = profile_data["stock"].get(product_name, {"current_quantity": 0.0})
        
        if product:
            percent_exp = self.business_logic.calculate_percent_expenses(
                product['cost_price'], product['profit']
            )
            percent_profit = self.business_logic.calculate_percent_profit(
                product['cost_price'], product['profit']
            )
            
            info_text = (
                f"ЦЕНА: {product['cost_price']:.2f} ₽/кг | "
                f"ПРИБЫЛЬ: {product['profit']:.2f} ₽ ({percent_profit:.1f}%) | "
                f"ОСТАТОК: {stock_data['current_quantity']:.2f} кг"
            )
            self.info_label.text = info_text

    def toggle_delivery(self, _instance) -> None:
        self.delivery_enabled = not self.delivery_enabled
        self.delivery_btn.text = 'ДОСТАВКА: ВКЛ' if self.delivery_enabled else 'ДОСТАВКА: ВЫКЛ'
        self.delivery_btn.background_color = COLORS['YELLOW'] if self.delivery_enabled else COLORS['ACCENT_RED']
        self.update_total()

    def add_item(self, _instance) -> None:
        product_name = self.product_btn.text
        if product_name == 'ВЫБЕРИТЕ ТОВАР':
            self.show_popup('ОШИБКА', 'Выберите товар')
            return
        
        qty, error = Validators.validate_positive_float(self.qty_input.text, "Количество")
        if error:
            self.show_popup('ОШИБКА', error)
            return
        
        profile_data = self.get_profile_data()
        stock_data = profile_data["stock"].get(product_name, {"current_quantity": 0.0})
        
        if qty > stock_data["current_quantity"]:
            self.show_popup(
                'ОШИБКА',
                f'Недостаточно товара. Доступно: {stock_data["current_quantity"]:.2f} кг'
            )
            return
        
        product = next((p for p in profile_data["products"] if p["name"] == product_name), None)
        if not product:
            self.show_popup('ОШИБКА', 'Товар не найден')
            return
        
        item = {
            "product": product_name,
            "quantity": qty,
            "cost_price": product["cost_price"],
            "total": qty * product["cost_price"]
        }
        
        self.order_items.append(item)
        
        item_label = Label(
            text=f'{product_name.upper()} × {qty:.1f} кг = {item["total"]:.2f} ₽',
            size_hint_y=None,
            height=dp(45),
            color=COLORS['TEXT_PRIMARY'],
            font_size=dp(16),
            halign='left',
            valign='middle'
        )
        item_label.bind(size=item_label.setter('text_size'))
        self.items_list.add_widget(item_label)
        self.update_total()

    def update_total(self) -> None:
        subtotal = sum(item["total"] for item in self.order_items)
        total_weight = sum(item["quantity"] for item in self.order_items)
        delivery = self.business_logic.calculate_delivery_cost(total_weight) if self.delivery_enabled and total_weight > 0 else 0
        total = subtotal + delivery
        self.total_label.text = f'ИТОГО: {total:.2f} ₽'

    def save_order(self, _instance) -> None:
        if not self.order_items:
            self.show_popup('ОШИБКА', 'Добавьте товары в заказ')
            return
        
        profile_data = self.get_profile_data()
        
        # Проверка остатков
        stock_check = defaultdict(float)
        for item in self.order_items:
            stock_check[item["product"]] += item["quantity"]
        
        for product, required in stock_check.items():
            available = profile_data["stock"].get(product, {"current_quantity": 0.0})["current_quantity"]
            if required > available:
                self.show_popup(
                    'ОШИБКА',
                    f'Недостаточно {product}. Требуется: {required:.2f} кг, доступно: {available:.2f} кг'
                )
                return
        
        subtotal = sum(item["total"] for item in self.order_items)
        total_weight = sum(item["quantity"] for item in self.order_items)
        delivery = self.business_logic.calculate_delivery_cost(total_weight) if self.delivery_enabled else 0
        total = subtotal + delivery
        
        order_date = datetime.now().strftime("%Y-%m-%d")
        operation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_number = self.current_order_number
        
        # Списание со склада
        for item in self.order_items:
            product_name = item["product"]
            qty = item["quantity"]
            stock_data = profile_data["stock"][product_name]
            prev_qty = stock_data["current_quantity"]
            prev_value = stock_data["total_value"]
            stock_data["current_quantity"] -= qty
            avg_price = prev_value / prev_qty if prev_qty > 0 else 0
            stock_data["total_value"] = stock_data["current_quantity"] * avg_price if prev_qty > 0 else 0
            stock_data["history"].append({
                "date": operation_time,
                "quantity": -qty,
                "price_per_kg": avg_price,
                "operation": "списание",
                "total_amount": qty * avg_price if prev_qty > 0 else 0,
                "balance_after": stock_data["current_quantity"]
            })
        
        # Сохранение заказа
        profile_data["orders"].append({
            "number": order_number,
            "date": order_date,
            "items": self.order_items,
            "subtotal": subtotal,
            "delivery_cost": delivery,
            "total": total
        })
        
        # Обновление статистики
        if order_date not in profile_data["daily_stats"]:
            profile_data["daily_stats"][order_date] = {
                "orders_count": 0,
                "delivery_count": 0,
                "delivery_sum": 0.0,
                "total_revenue": 0.0
            }
        
        stats = profile_data["daily_stats"][order_date]
        stats["orders_count"] += 1
        if self.delivery_enabled:
            stats["delivery_count"] += 1
            stats["delivery_sum"] += delivery
        stats["total_revenue"] += total
        
        profile_data["next_order_number"] = order_number + 1
        self.save_profile_data(profile_data)
        
        # Сброс формы
        self.order_items = []
        self.items_list.clear_widgets()
        self.product_btn.text = 'ВЫБЕРИТЕ ТОВАР'
        self.product_btn.color = COLORS['TEXT_HINT']
        self.qty_input.text = '1.0'
        self.total_label.text = 'ИТОГО: 0.00 ₽'
        self.info_label.text = ''
        
        self.show_popup(
            'УСПЕХ',
            f'Заказ №{order_number} сохранен!\nИтого: {total:.2f} ₽',
            callback=lambda: setattr(self.manager, 'current', 'profile')
        )


class SalesAnalysisScreen(BaseScreen):
    """Экран анализа продаж."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.date_from_input = None
        self.date_to_input = None
        self.product_dropdown_btn = None
        self.product_list: List[str] = []
        self.analysis_scroll = None
        self.analysis_container = None
        self.analysis_list = None
        self._table_w: int = get_table_width()
        self.build_ui()

    def build_ui(self) -> None:
        self._table_w = get_table_width()
        layout = BoxLayout(orientation='vertical', padding=[Dimensions.PADDING, dp(10)], spacing=dp(8))
        layout.add_widget(UIComponents.create_back_button('profile', 'НАЗАД'))
        
        title = Label(
            text='АНАЛИЗ ПРОДАЖ',
            size_hint_y=None,
            height=dp(55),
            font_size=dp(25),
            bold=True,
            color=COLORS['YELLOW'],
            halign='center',
            valign='middle'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)
        
        hint_label = Label(
            text='Выберите период и товар для анализа',
            size_hint_y=None,
            height=dp(32),
            font_size=dp(16),
            color=COLORS['TEXT_HINT'],
            halign='center',
            valign='middle',
            italic=True
        )
        hint_label.bind(size=hint_label.setter('text_size'))
        layout.add_widget(hint_label)
        
        filters_layout = BoxLayout(orientation='vertical', size_hint_y=0.26, spacing=dp(14))
        
        # Дата от
        date_from_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(80))
        date_from_layout.add_widget(Label(
            text='НАЧАЛО ПЕРИОДА:',
            color=COLORS['YELLOW'],
            font_size=dp(17),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.date_from_input = UIComponents.create_input_field(
            hint_text='ГГГГ-ММ-ДД',
            text=(date.today() - timedelta(days=30)).isoformat()
        )
        date_from_layout.add_widget(self.date_from_input)
        filters_layout.add_widget(date_from_layout)
        
        # Дата до
        date_to_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(80))
        date_to_layout.add_widget(Label(
            text='КОНЕЦ ПЕРИОДА:',
            color=COLORS['YELLOW'],
            font_size=dp(17),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.date_to_input = UIComponents.create_input_field(
            hint_text='ГГГГ-ММ-ДД',
            text=date.today().isoformat()
        )
        date_to_layout.add_widget(self.date_to_input)
        filters_layout.add_widget(date_to_layout)
        
        # Выбор товара
        product_filter_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(80))
        product_filter_layout.add_widget(Label(
            text='ФИЛЬТР ПО ТОВАРУ:',
            color=COLORS['YELLOW'],
            font_size=dp(17),
            bold=True,
            size_hint_y=None,
            height=dp(32),
            halign='left'
        ))
        
        self.product_dropdown_btn = Button(
            text='ВСЕ ТОВАРЫ',
            size_hint_y=None,
            height=Dimensions.INPUT_HEIGHT,
            background_normal='',
            background_color=COLORS['CARD_BG'],
            color=COLORS['YELLOW'],
            font_size=dp(18),
            bold=True,
            halign='left',
            valign='middle'
        )
        self.product_dropdown_btn.bind(size=self.product_dropdown_btn.setter('text_size'))
        self.product_dropdown_btn.bind(on_press=self.show_product_dropdown)
        
        # Добавляем границу
        with self.product_dropdown_btn.canvas.after:
            Color(*COLORS['BORDER'])
            self.product_dropdown_btn.border = Line(rectangle=(self.product_dropdown_btn.x, self.product_dropdown_btn.y, self.product_dropdown_btn.width, self.product_dropdown_btn.height), width=1.5)
        
        def update_border(instance, value):
            instance.border.rectangle = (instance.x, instance.y, instance.width, instance.height)
        
        self.product_dropdown_btn.bind(pos=update_border, size=update_border)
        
        product_filter_layout.add_widget(self.product_dropdown_btn)
        filters_layout.add_widget(product_filter_layout)
        
        layout.add_widget(filters_layout)
        
        # Кнопки фильтрации
        btn_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(58), spacing=dp(14))
        apply_btn = UIComponents.create_primary_button('ПРИМЕНИТЬ')
        clear_btn = UIComponents.create_secondary_button('СБРОСИТЬ', color=COLORS['ACCENT_AMBER'])
        apply_btn.bind(on_press=self.load_analysis)
        clear_btn.bind(on_press=self.clear_filters)
        btn_layout.add_widget(apply_btn)
        btn_layout.add_widget(clear_btn)
        layout.add_widget(btn_layout)
        
        # Результаты анализа
        results_title = Label(
            text='РЕЗУЛЬТАТЫ АНАЛИЗА (свайп влево/вправо)',
            size_hint_y=None,
            height=dp(38),
            font_size=dp(18),
            bold=True,
            color=COLORS['YELLOW'],
            halign='center',
            valign='middle'
        )
        results_title.bind(size=results_title.setter('text_size'))
        layout.add_widget(results_title)
        
        scroll = ScrollView(
            size_hint_y=0.48,
            do_scroll_x=True,
            do_scroll_y=True,
            bar_width=dp(8),
            scroll_type=['bars', 'content']
        )
        self.analysis_scroll = scroll
        w = self._table_w
        self.analysis_container = BoxLayout(orientation='vertical', size_hint_x=None, width=w)
        self.analysis_list = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, size_hint_x=None, width=w)
        self.analysis_list.bind(minimum_height=self.analysis_list.setter('height'))
        self.analysis_container.add_widget(self.analysis_list)
        scroll.add_widget(self.analysis_container)
        layout.add_widget(scroll)
        
        self.add_widget(layout)

    def on_enter(self) -> None:
        self.load_products_for_dropdown()
        self.load_analysis(None)

    def load_products_for_dropdown(self) -> None:
        profile_data = self.get_profile_data()
        products = [p["name"] for p in profile_data.get("products", [])]
        self.product_list = ["ВСЕ ТОВАРЫ"] + sorted(products)

    def show_product_dropdown(self, _instance) -> None:
        dropdown = DropDown()
        for product_name in self.product_list:
            btn = Button(
                text=product_name.upper(),
                size_hint_y=None,
                height=dp(50),
                background_normal='',
                background_color=COLORS['CARD_BG'],
                color=COLORS['YELLOW'],
                font_size=dp(17),
                bold=True
            )
            btn.bind(on_release=lambda btn, p=product_name: self.select_product(p, dropdown))
            dropdown.add_widget(btn)
        
        dropdown.open(self.product_dropdown_btn)

    def select_product(self, product_name: str, dropdown: DropDown) -> None:
        self.product_dropdown_btn.text = product_name.upper()
        self.product_dropdown_btn.color = COLORS['YELLOW']
        dropdown.dismiss()

    def clear_filters(self, _instance) -> None:
        self.date_from_input.text = (date.today() - timedelta(days=30)).isoformat()
        self.date_to_input.text = date.today().isoformat()
        self.product_dropdown_btn.text = 'ВСЕ ТОВАРЫ'
        self.product_dropdown_btn.color = COLORS['YELLOW']
        self.load_analysis(None)

    def load_analysis(self, _instance) -> None:
        self.analysis_list.clear_widgets()
        self._table_w = get_table_width()
        self.analysis_container.width = self._table_w
        
        date_from, error = Validators.validate_date(self.date_from_input.text)
        if error:
            self.show_popup('ОШИБКА', f'Неверный формат даты "от": {error}')
            return
        
        date_to, error = Validators.validate_date(self.date_to_input.text)
        if error:
            self.show_popup('ОШИБКА', f'Неверный формат даты "до": {error}')
            return
        
        if date_from > date_to:
            self.show_popup('ОШИБКА', 'Дата "от" не может быть больше даты "до"')
            return
        
        selected_product = self.product_dropdown_btn.text
        filter_by_product = selected_product != "ВСЕ ТОВАРЫ"
        
        profile_data = self.get_profile_data()
        orders = profile_data.get("orders", [])
        products = {p["name"]: p for p in profile_data.get("products", [])}
        
        sales_data = defaultdict(lambda: defaultdict(lambda: {'qty': 0.0, 'sum': 0.0}))
        
        for order in orders:
            try:
                order_date = datetime.strptime(order["date"], "%Y-%m-%d").date()
                if not (date_from <= order_date <= date_to):
                    continue
                
                for item in order["items"]:
                    if filter_by_product and item["product"] != selected_product:
                        continue
                    
                    product_name = item["product"]
                    qty = item["quantity"]
                    total = item["total"]
                    
                    sales_data[order["date"]][product_name]['qty'] += qty
                    sales_data[order["date"]][product_name]['sum'] += total
            except Exception:
                continue
        
        # Заголовок таблицы
        header_labels = [
            ("ДАТА", 0.14),
            ("ТОВАР", 0.24),
            ("КОЛИЧЕСТВО", 0.14),
            ("СУММА В ДЕНЬ", 0.16),
            ("ВЫРУЧКА", 0.16),
            ("ЗАТРАТЫ", 0.16)
        ]
        
        header_card = UIComponents.create_table_header(header_labels, width=self._table_w)
        self.analysis_list.add_widget(header_card)
        
        # Проверка на отсутствие данных
        if not sales_data:
            empty_label = Label(
                text='НЕТ ДАННЫХ ДЛЯ ВЫБРАННОГО ПЕРИОДА',
                size_hint_y=None,
                height=dp(75),
                color=COLORS['TEXT_SECONDARY'],
                font_size=dp(20),
                bold=True,
                halign='center',
                valign='middle'
            )
            empty_label.bind(size=empty_label.setter('text_size'))
            self.analysis_list.add_widget(empty_label)
            
            hint_label = Label(
                text='Измените период или добавьте заказы',
                size_hint_y=None,
                height=dp(45),
                color=COLORS['TEXT_HINT'],
                font_size=dp(16),
                halign='center',
                valign='middle',
                italic=True
            )
            hint_label.bind(size=hint_label.setter('text_size'))
            self.analysis_list.add_widget(hint_label)
            return
        
        # Заполнение таблицы
        row_index = 0
        for day_date_str, products_data in sorted(sales_data.items()):
            for product_name, values in products_data.items():
                qty = values['qty']
                daily_sum = values['sum']
                product = products.get(product_name, {})
                profit_pct = product.get("percent_profit", 0.0)
                expense_pct = product.get("percent_expenses", 0.0)
                profit_calc = (daily_sum * profit_pct) / 100.0
                expense_calc = (daily_sum * expense_pct) / 100.0
                
                bg_color = COLORS['CARD_BG'] if row_index % 2 == 0 else get_color_from_hex('#222222')
                
                card = BoxLayout(
                    orientation='horizontal',
                    size_hint_y=None,
                    height=dp(62),
                    padding=[dp(12), dp(8)],
                    spacing=dp(6),
                    size_hint_x=None,
                    width=self._table_w
                )
                
                with card.canvas.before:
                    Color(*bg_color)
                    card.rect = Rectangle(pos=card.pos, size=card.size)
                    Color(*COLORS['BORDER'])
                    card.line = Line(points=[card.x, card.y, card.right, card.y], width=0.8)
                
                def update_line(instance, value):
                    instance.rect.pos = instance.pos
                    instance.rect.size = instance.size
                    instance.line.points = [instance.x, instance.y, instance.right, instance.y]
                
                card.bind(pos=update_line, size=update_line)
                
                for text, width_ratio, color in [
                    (day_date_str, 0.14, COLORS['TEXT_PRIMARY']),
                    (product_name.upper(), 0.24, COLORS['YELLOW']),
                    (f"{qty:.1f} кг", 0.14, COLORS['ACCENT_AMBER']),
                    (f"{daily_sum:,.0f} ₽".replace(",", " "), 0.16, COLORS['ACCENT_GREEN']),
                    (f"{profit_calc:,.0f} ₽".replace(",", " "), 0.16, COLORS['ACCENT_GREEN']),
                    (f"{expense_calc:,.0f} ₽".replace(",", " "), 0.16, COLORS['ACCENT_AMBER'])
                ]:
                    label = Label(
                        text=text,
                        font_size=dp(16),
                        bold=(width_ratio > 0.15),
                        color=color,
                        size_hint_x=width_ratio,
                        halign='center',
                        valign='middle'
                    )
                    label.bind(size=label.setter('text_size'))
                    card.add_widget(label)
                
                self.analysis_list.add_widget(card)
                row_index += 1
        
        # Итоговая строка
        total_qty = sum(v['qty'] for pd in sales_data.values() for v in pd.values())
        total_sum = sum(v['sum'] for pd in sales_data.values() for v in pd.values())
        total_profit = sum(
            (v['sum'] * products.get(p, {}).get("percent_profit", 0.0)) / 100.0
            for pd in sales_data.values() for p, v in pd.items()
        )
        total_expense = sum(
            (v['sum'] * products.get(p, {}).get("percent_expenses", 0.0)) / 100.0
            for pd in sales_data.values() for p, v in pd.items()
        )
        
        total_card = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(68),
            padding=[dp(12), dp(8)],
            spacing=dp(6),
            size_hint_x=None,
            width=self._table_w
        )
        
        with total_card.canvas.before:
            Color(*get_color_from_hex('#333300'))
            total_card.rect = Rectangle(pos=total_card.pos, size=total_card.size)
            Color(*COLORS['YELLOW'])
            total_card.border = Line(rectangle=(total_card.x, total_card.y, total_card.width, total_card.height), width=2.0)
        
        def update_total_rect(instance, value):
            instance.rect.pos = instance.pos
            instance.rect.size = instance.size
        
        total_card.bind(pos=update_total_rect, size=update_total_rect)
        
        total_items = [
            ("ИТОГО", 0.14, COLORS['YELLOW']),
            ("", 0.24, COLORS['TEXT_PRIMARY']),
            (f"{total_qty:.1f} кг", 0.14, COLORS['ACCENT_AMBER']),
            (f"{total_sum:,.0f} ₽".replace(",", " "), 0.16, COLORS['ACCENT_GREEN']),
            (f"{total_profit:,.0f} ₽".replace(",", " "), 0.16, COLORS['ACCENT_GREEN']),
            (f"{total_expense:,.0f} ₽".replace(",", " "), 0.16, COLORS['ACCENT_AMBER'])
        ]
        
        for text, width_ratio, color in total_items:
            label = Label(
                text=text,
                font_size=dp(17),
                bold=True,
                color=color,
                size_hint_x=width_ratio,
                halign='center',
                valign='middle'
            )
            label.bind(size=label.setter('text_size'))
            total_card.add_widget(label)
        
        self.analysis_list.add_widget(total_card)


class OrderHistoryScreen(BaseScreen):
    """Экран истории заказов."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history_list = None
        self.stats_scroll = None
        self.stats_container = None
        self.stats_list = None
        self._table_w: int = get_table_width()
        self.build_ui()

    def build_ui(self) -> None:
        self._table_w = get_table_width()
        layout = BoxLayout(orientation='vertical', padding=[Dimensions.PADDING, dp(10)], spacing=dp(8))
        layout.add_widget(UIComponents.create_back_button('profile', 'НАЗАД'))
        
        title = Label(
            text='ИСТОРИЯ ЗАКАЗОВ',
            size_hint_y=None,
            height=dp(50),
            font_size=dp(24),
            bold=True,
            color=COLORS['YELLOW'],
            halign='center',
            valign='middle'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)
        
        scroll = ScrollView(size_hint_y=0.24)
        self.history_list = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=[0, dp(5)])
        self.history_list.bind(minimum_height=self.history_list.setter('height'))
        scroll.add_widget(self.history_list)
        layout.add_widget(scroll)
        
        stats_title = Label(
            text='ДНЕВНАЯ СТАТИСТИКА (свайп влево/вправо)',
            size_hint_y=None,
            height=dp(36),
            font_size=dp(18),
            bold=True,
            color=COLORS['YELLOW'],
            halign='center',
            valign='middle'
        )
        stats_title.bind(size=stats_title.setter('text_size'))
        layout.add_widget(stats_title)
        
        stats_scroll = ScrollView(
            size_hint_y=0.56,
            do_scroll_x=True,
            do_scroll_y=True,
            bar_width=dp(8),
            scroll_type=['bars', 'content']
        )
        self.stats_scroll = stats_scroll
        w = self._table_w
        self.stats_container = BoxLayout(orientation='vertical', size_hint_x=None, width=w)
        self.stats_list = GridLayout(cols=1, spacing=dp(7), size_hint_y=None, size_hint_x=None, width=w)
        self.stats_list.bind(minimum_height=self.stats_list.setter('height'))
        self.stats_container.add_widget(self.stats_list)
        stats_scroll.add_widget(self.stats_container)
        layout.add_widget(stats_scroll)
        
        self.add_widget(layout)

    def on_enter(self) -> None:
        self.load_history()
        self.load_daily_stats()

    def load_history(self) -> None:
        self.history_list.clear_widgets()
        profile_data = self.get_profile_data()
        orders = profile_data.get("orders", [])
        
        if not orders:
            empty_label = Label(
                text='НЕТ ЗАВЕРШЕННЫХ ЗАКАЗОВ',
                size_hint_y=None,
                height=dp(65),
                color=COLORS['TEXT_SECONDARY'],
                font_size=dp(21),
                bold=True,
                halign='center',
                valign='middle'
            )
            empty_label.bind(size=empty_label.setter('text_size'))
            self.history_list.add_widget(empty_label)
            return
        
        for order in sorted(orders, key=lambda x: x["number"], reverse=True)[:15]:
            card = BoxLayout(
                orientation='vertical',
                size_hint_y=None,
                height=dp(105),
                padding=[dp(14), dp(8)],
                spacing=dp(4)
            )
            
            with card.canvas.before:
                Color(*COLORS['CARD_BG'])
                card.rect = Rectangle(pos=card.pos, size=card.size)
            
            def update_rect(instance, value):
                instance.rect.pos = instance.pos
                instance.rect.size = instance.size
            
            card.bind(pos=update_rect, size=update_rect)
            
            num_label = Label(
                text=f"ЗАКАЗ №{order['number']} ОТ {order['date']}",
                font_size=dp(17),
                bold=True,
                color=COLORS['YELLOW'],
                size_hint_y=None,
                height=dp(30),
                halign='left',
                valign='middle'
            )
            num_label.bind(size=num_label.setter('text_size'))
            
            items_label = Label(
                text=f"ТОВАРОВ: {len(order['items'])} | ВЕС: {sum(i['quantity'] for i in order['items']):.1f} кг",
                font_size=dp(15),
                color=COLORS['TEXT_PRIMARY'],
                size_hint_y=None,
                height=dp(28),
                halign='left',
                valign='middle'
            )
            items_label.bind(size=items_label.setter('text_size'))
            
            total_label = Label(
                text=f"ИТОГО: {order['total']:.2f} ₽ (доставка: {order['delivery_cost']} ₽)",
                font_size=dp(16),
                color=COLORS['ACCENT_GREEN'],
                size_hint_y=None,
                height=dp(30),
                halign='left',
                valign='middle'
            )
            total_label.bind(size=total_label.setter('text_size'))
            
            card.add_widget(num_label)
            card.add_widget(items_label)
            card.add_widget(total_label)
            self.history_list.add_widget(card)

    def load_daily_stats(self) -> None:
        self.stats_list.clear_widgets()
        self._table_w = get_table_width()
        self.stats_container.width = self._table_w
        
        profile_data = self.get_profile_data()
        daily_stats = profile_data.get("daily_stats", {})
        
        header_labels = [
            ("ДАТА", 0.18),
            ("ЗАКАЗОВ", 0.18),
            ("ДОСТАВКА", 0.18),
            ("СУММА ДЕНЬ", 0.18),
            ("СУММА ДОСТ", 0.18),
            ("ВЫРУЧКА", 0.18)
        ]
        
        header_card = UIComponents.create_table_header(header_labels, width=self._table_w)
        self.stats_list.add_widget(header_card)
        
        for date_key, data in sorted(daily_stats.items(), reverse=True):
            card = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(58),
                padding=[dp(10), dp(6)],
                spacing=dp(6),
                size_hint_x=None,
                width=self._table_w
            )
            
            with card.canvas.before:
                Color(*COLORS['CARD_BG'])
                card.rect = Rectangle(pos=card.pos, size=card.size)
                Color(*COLORS['BORDER'])
                card.line = Line(points=[card.x, card.y, card.right, card.y], width=0.7)
            
            def update_line(instance, value):
                instance.rect.pos = instance.pos
                instance.rect.size = instance.size
                instance.line.points = [instance.x, instance.y, instance.right, instance.y]
            
            card.bind(pos=update_line, size=update_line)
            
            date_label = Label(
                text=date_key,
                font_size=dp(16),
                bold=True,
                color=COLORS['TEXT_PRIMARY'],
                size_hint_x=0.18,
                halign='center',
                valign='middle'
            )
            date_label.bind(size=date_label.setter('text_size'))
            
            orders_label = Label(
                text=str(data["orders_count"]),
                font_size=dp(17),
                bold=True,
                color=COLORS['YELLOW'],
                size_hint_x=0.18,
                halign='center',
                valign='middle'
            )
            orders_label.bind(size=orders_label.setter('text_size'))
            
            delivery_label = Label(
                text=str(data["delivery_count"]),
                font_size=dp(17),
                bold=True,
                color=COLORS['ACCENT_AMBER'],
                size_hint_x=0.18,
                halign='center',
                valign='middle'
            )
            delivery_label.bind(size=delivery_label.setter('text_size'))
            
            sum_day_label = Label(
                text=f"{int(data['total_revenue']):,}".replace(",", " "),
                font_size=dp(17),
                bold=True,
                color=COLORS['ACCENT_GREEN'],
                size_hint_x=0.18,
                halign='center',
                valign='middle'
            )
            sum_day_label.bind(size=sum_day_label.setter('text_size'))
            
            delivery_sum_label = Label(
                text=f"{int(data['delivery_sum']):,}".replace(",", " "),
                font_size=dp(17),
                bold=True,
                color=COLORS['ACCENT_AMBER'],
                size_hint_x=0.18,
                halign='center',
                valign='middle'
            )
            delivery_sum_label.bind(size=delivery_sum_label.setter('text_size'))
            
            revenue_label = Label(
                text=f"{int(data['total_revenue'] - data['delivery_sum']):,}".replace(",", " "),
                font_size=dp(17),
                bold=True,
                color=COLORS['ACCENT_GREEN'],
                size_hint_x=0.18,
                halign='center',
                valign='middle'
            )
            revenue_label.bind(size=revenue_label.setter('text_size'))
            
            card.add_widget(date_label)
            card.add_widget(orders_label)
            card.add_widget(delivery_label)
            card.add_widget(sum_day_label)
            card.add_widget(delivery_sum_label)
            card.add_widget(revenue_label)
            self.stats_list.add_widget(card)


class StockHistoryScreen(BaseScreen):
    """Экран истории операций со складом."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history_container = None
        self.history_list = None
        self.build_ui()

    def build_ui(self) -> None:
        layout = BoxLayout(orientation='vertical', padding=Dimensions.PADDING, spacing=Dimensions.SPACING)
        layout.add_widget(UIComponents.create_back_button('warehouse', 'НАЗАД'))
        
        title = Label(
            text='ИСТОРИЯ ОПЕРАЦИЙ СО СКЛАДОМ',
            size_hint_y=None,
            height=dp(52),
            font_size=dp(22),
            bold=True,
            color=COLORS['YELLOW'],
            halign='center',
            valign='middle'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)
        
        scroll = ScrollView(
            size_hint_y=0.88,
            do_scroll_x=True,
            bar_width=dp(10),
            scroll_type=['bars', 'content']
        )
        
        self.history_container = BoxLayout(orientation='vertical', size_hint_x=None, width=1050)
        self.history_list = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, size_hint_x=None, width=1050)
        self.history_list.bind(minimum_height=self.history_list.setter('height'))
        self.history_container.add_widget(self.history_list)
        scroll.add_widget(self.history_container)
        layout.add_widget(scroll)
        
        self.add_widget(layout)

    def on_enter(self) -> None:
        self.load_history()

    def load_history(self) -> None:
        self.history_list.clear_widgets()
        self.history_container.width = 1050
        
        profile_data = self.get_profile_data()
        stock_data = profile_data.get("stock", {})
        
        if not stock_data:
            empty_label = Label(
                text='НЕТ ИСТОРИИ ОПЕРАЦИЙ СО СКЛАДОМ',
                size_hint_y=None,
                height=dp(65),
                color=COLORS['TEXT_SECONDARY'],
                font_size=dp(20),
                bold=True,
                halign='center',
                valign='middle'
            )
            empty_label.bind(size=empty_label.setter('text_size'))
            self.history_list.add_widget(empty_label)
            return
        
        all_operations = []
        for product_name, data in stock_data.items():
            history = data.get("history", [])
            for op in history:
                op_dict = {
                    "date": op.get("date", " "),
                    "product": product_name,
                    "operation": op.get("operation", "Неизвестно"),
                    "quantity": op.get("quantity", 0.0),
                    "price_per_kg": op.get("price_per_kg", 0.0),
                    "total_amount": op.get("total_amount", 0.0),
                    "balance_after": op.get("balance_after", 0.0)
                }
                all_operations.append(op_dict)
        
        all_operations.sort(key=lambda x: x["date"], reverse=True)
        
        header_labels = [
            ("ДАТА", 0.18),
            ("ТОВАР", 0.26),
            ("ОПЕРАЦИЯ", 0.18),
            ("КОЛИЧЕСТВО", 0.12),
            ("ЦЕНА ЗАКУПКИ", 0.13),
            ("СУММА", 0.13)
        ]
        
        header_card = UIComponents.create_table_header(header_labels, width=1050)
        self.history_list.add_widget(header_card)
        
        for op in all_operations[:50]:
            card = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(55),
                padding=[dp(10), dp(6)],
                spacing=dp(6),
                size_hint_x=None,
                width=1050
            )
            
            bg_color = COLORS['CARD_BG'] if len(self.history_list.children) % 2 == 0 else get_color_from_hex('#222222')
            
            with card.canvas.before:
                Color(*bg_color)
                card.rect = Rectangle(pos=card.pos, size=card.size)
            
            def update_rect(instance, value):
                instance.rect.pos = instance.pos
                instance.rect.size = instance.size
            
            card.bind(pos=update_rect, size=update_rect)
            
            for text, width_ratio in [
                (op["date"], 0.18),
                (op["product"].upper(), 0.26),
                (op["operation"].upper(), 0.18),
                (f"{op['quantity']:.2f}", 0.12),
                (f"{op['price_per_kg']:.2f}", 0.13),
                (f"{op['total_amount']:.2f}", 0.13)
            ]:
                label = Label(
                    text=text,
                    font_size=dp(15),
                    color=COLORS['TEXT_PRIMARY'],
                    size_hint_x=width_ratio,
                    halign='center',
                    valign='middle'
                )
                label.bind(size=label.setter('text_size'))
                card.add_widget(label)
            
            self.history_list.add_widget(card)


class OrderApp(App):
    """Главное приложение системы управления заказами."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_profile: Optional[str] = None
        self.profile_data: Dict = {}
        self.product_to_edit: Optional[Dict] = None
        self.data_manager = DataManager()
        self.business_logic = BusinessLogic()

    def build(self) -> ScreenManager:
        # Устанавливаем черный фон для всего приложения
        Window.clearcolor = COLORS['BACKGROUND']
        
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(ProfileScreen(name='profile'))
        sm.add_widget(ProductsScreen(name='products'))
        sm.add_widget(AddProductScreen(name='add_product'))
        sm.add_widget(EditProductScreen(name='edit_product'))
        sm.add_widget(WarehouseScreen(name='warehouse'))
        sm.add_widget(AddStockScreen(name='add_stock'))
        sm.add_widget(CreateOrderScreen(name='create_order'))
        sm.add_widget(SalesAnalysisScreen(name='sales_analysis'))
        sm.add_widget(OrderHistoryScreen(name='order_history'))
        sm.add_widget(StockHistoryScreen(name='stock_history'))
        return sm

    def on_start(self):
        """Инициализация при запуске приложения."""
        # Запрос разрешений для Android
        self.request_android_permissions()

    def request_android_permissions(self) -> None:
        """Запрос разрешений для Android (если доступно)."""
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            ActivityCompat = autoclass('androidx.core.app.ActivityCompat')
            Manifest = autoclass('android.Manifest$permission')
            
            activity = PythonActivity.mActivity
            permissions = [
                Manifest.READ_EXTERNAL_STORAGE,
                Manifest.WRITE_EXTERNAL_STORAGE
            ]
            
            for permission in permissions:
                if ActivityCompat.checkSelfPermission(activity, permission) != 0:
                    ActivityCompat.requestPermissions(activity, [permission], 1)
        except Exception:
            pass


if __name__ == '__main__':
    OrderApp().run()