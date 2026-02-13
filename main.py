"""
Мобильное приложение для управления заказами и складом
ПОЛНОСТЬЮ БЕЗ EXCEL — все данные в единой JSON-базе
ВЕРСИЯ ДЛЯ ANDROID: все пути к данным используют user_data_dir
"""
import os
import json
import sys
import shutil
from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple

# === ИМПОРТЫ KIVY ===
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
from kivy.clock import Clock

# === НАСТРОЙКИ ОКНА (адаптивность) ===
# На Android не меняем размер — полноэкранный режим; на ПК — удобное окно
try:
    from kivy.utils import platform
    if platform != 'android':
        Window.size = (360, 640)
except Exception:
    Window.size = (360, 640)


def get_table_width():
    """Ширина таблицы для горизонтального скролла: больше экрана на всех устройствах."""
    return max(int(Window.width * 1.85), 700)

# === ЦВЕТОВАЯ СХЕМА (в духе современного банковского UI) ===
COLORS = {
    'WHITE': (1.0, 1.0, 1.0, 1),
    'LIGHT_BG': (0.97, 0.98, 1.0, 1),
    'DARK_BLUE': (0.08, 0.35, 0.65, 1),
    'DARK_TEXT': (0.12, 0.12, 0.14, 1),
    'BLACK': (0.0, 0.0, 0.0, 1),
    'MEDIUM_GREY': (0.45, 0.45, 0.5, 1),
    'LIGHT_GREY': (0.92, 0.93, 0.95, 1),
    'RED': (0.85, 0.20, 0.22, 1),
    'GREEN': (0.18, 0.62, 0.35, 1),
    'AMBER': (0.95, 0.55, 0.12, 1),
    'PURPLE': (0.48, 0.25, 0.72, 1),
    'ORANGE': (0.95, 0.48, 0.18, 1),
    'TEAL': (0.0, 0.55, 0.58, 1),
    'PINK': (0.82, 0.22, 0.48, 1),
    # Плитки меню (насыщенные, но не кислотные)
    'TILE_BLUE': (0.12, 0.42, 0.78, 1),
    'TILE_GREEN': (0.20, 0.62, 0.38, 1),
    'TILE_TEAL': (0.0, 0.52, 0.55, 1),
    'TILE_VIOLET': (0.50, 0.28, 0.72, 1),
    'TILE_AMBER': (0.95, 0.58, 0.15, 1),
    'TILE_PINK': (0.85, 0.25, 0.48, 1),
}
# Единые высоты кнопок (dp)
BTN_TILE_H = 118
BTN_ACTION_H = 52
BTN_BACK_H = 48

# ============================================================================
# МОДУЛЬ: БИЗНЕС-ЛОГИКА (ВСЕ РАСЧЕТЫ СОХРАНЕНЫ БЕЗ ИЗМЕНЕНИЙ)
# ============================================================================
class BusinessLogic:
    """Центральный модуль бизнес-логики — все расчеты оригинальные"""
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
        """Оригинальная логика доставки:
        - >=5 кг → 100 ₽
        - >=3 кг → 150 ₽
        - <3 кг → 200 ₽
        """
        if weight >= 5:
            return 100
        elif weight >= 3:
            return 150
        else:
            return 200

# ============================================================================
# МОДУЛЬ: УПРАВЛЕНИЕ ДАННЫМИ (СОВМЕСТИМОСТЬ С ANDROID)
# ============================================================================
class DataManager:
    """Управление данными с использованием user_data_dir для совместимости с Android"""
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._last_save = datetime.now()
        self._profiles: Optional[Dict] = None
        self._init_directories()

    def _init_directories(self):
        """Создание директорий при старте с использованием user_data_dir"""
        from kivy.app import App
        app = App.get_running_app()
        self.data_dir = app.user_data_dir
        self.profiles_file = os.path.join(self.data_dir, "profiles.json")
        self.backup_dir = os.path.join(self.data_dir, "backups")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        if not os.path.exists(self.profiles_file) or os.path.getsize(self.profiles_file) == 0:
            self._save_safe({}, self.profiles_file)
            print(f"[OK] Создан файл профилей: {self.profiles_file}")
 
    def _create_backup(self, filepath: str) -> str:
        """Создание резервной копии перед записью"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{os.path.basename(filepath)}.{timestamp}.bak"
        backup_path = os.path.join(self.backup_dir, backup_name)
        try:
            if os.path.exists(filepath):
                shutil.copy2(filepath, backup_path)
            # Удаление старых бэков (>7 дней)
            self._cleanup_old_backups()
            return backup_path
        except Exception as e:
            print(f"[!] Предупреждение: не удалось создать бэкап: {e}")
            return ""

    def _cleanup_old_backups(self, days: int = 7):
        """Очистка бэков старше N дней"""
        cutoff = datetime.now() - timedelta(days=days)
        for fname in os.listdir(self.backup_dir):
            if fname.endswith('.bak'):
                path = os.path.join(self.backup_dir, fname)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(path))
                    if mtime < cutoff:
                        os.remove(path)
                        print(f"[X] Удален старый бэкап: {fname}")
                except:
                    pass

    def _save_safe(self, data: Dict, filepath: str):
        """Безопасная запись с резервным копированием"""
        try:
            self._create_backup(filepath)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._last_save = datetime.now()
        except Exception as e:
            print(f"[!] Ошибка сохранения {filepath}: {e}")
            raise

    def _load_safe(self, filepath: str) -> Dict:
        """Безопасная загрузка с восстановлением из бэкапа при ошибке"""
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
        except json.JSONDecodeError as e:
            print(f"[!] JSON ошибка в {filepath}: {e}")
            # Попытка восстановления из последнего бэкапа
            backups = sorted(
                [f for f in os.listdir(self.backup_dir) if f.startswith(os.path.basename(filepath))],
                reverse=True
            )
            if backups:
                backup_path = os.path.join(self.backup_dir, backups[0])
                print(f"[<-] Восстановление из бэкапа: {backups[0]}")
                try:
                    with open(backup_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except:
                    return {}
            return {}
        except Exception as e:
            print(f"[!] Ошибка загрузки {filepath}: {e}")
            return {}

    def get_profiles(self) -> Dict:
        """Получение профилей с кэшированием"""
        if self._profiles is None:
            self._profiles = self._load_safe(self.profiles_file)
        return self._profiles

    def save_profiles(self, profiles: Dict):
        """Сохранение профилей с обновлением кэша"""
        self._save_safe(profiles, self.profiles_file)
        self._profiles = profiles.copy()

    def get_profile_data(self, profile_name: str) -> Dict:
        """Получение данных профиля с инициализацией структуры по умолчанию"""
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

    def update_profile_data(self, profile_name: str, data: Dict):
        """Обновление данных профиля"""
        profiles = self.get_profiles()
        profiles[profile_name] = data
        self.save_profiles(profiles)

# ============================================================================
# МОДУЛЬ: ВАЛИДАЦИЯ И УТИЛИТЫ
# ============================================================================
class Validators:
    """Универсальные валидаторы для всех полей ввода"""
    @staticmethod
    def validate_positive_float(text: str, field_name: str = "Значение") -> Tuple[Optional[float], Optional[str]]:
        """Валидация положительного числа с поддержкой запятой/точки"""
        try:
            value = float(text.replace(',', '.').strip())
            if value <= 0:
                return None, f"{field_name} должно быть положительным"
            return value, None
        except ValueError:
            return None, f"{field_name}: введите корректное число"

    @staticmethod
    def validate_non_empty(text: str, field_name: str = "Поле") -> Tuple[Optional[str], Optional[str]]:
        """Валидация непустой строки"""
        value = text.strip()
        if not value:
            return None, f"{field_name} не может быть пустым"
        return value, None

    @staticmethod
    def validate_date(text: str) -> Tuple[Optional[date], Optional[str]]:
        """Валидация даты в формате ГГГГ-ММ-ДД"""
        try:
            return datetime.strptime(text.strip(), "%Y-%m-%d").date(), None
        except ValueError:
            return None, "Неверный формат даты (ГГГГ-ММ-ДД)"

# ============================================================================
# МОДУЛЬ: UI КОМПОНЕНТЫ (БЕЗ ЭМОДЗИ)
# ============================================================================
class UIComponents:
    """Универсальные UI компоненты для повторного использования без эмодзи"""
    @staticmethod
    def create_popup(title: str, message: str, callback=None) -> Popup:
        """Унифицированный попап с текстовыми метками"""
        content = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        # Определение префикса по контексту
        prefix = ""
        if 'Ошибка' in title or 'ошибка' in message.lower():
            prefix = "[Ошибка] "
        elif 'Успех' in title or 'успех' in message.lower() or 'сохранен' in message.lower():
            prefix = "[Успех] "
        elif 'Подтверждение' in title or 'удалить' in message.lower():
            prefix = "[Подтверждение] "

        # Заголовок
        title_label = Label(
            text=f'{prefix}{title}',
            color=COLORS['DARK_BLUE'],
            font_size='21sp',
            bold=True,
            size_hint_y=None,
            height=45,
            halign='center'
        )
        title_label.bind(size=title_label.setter('text_size'))
        content.add_widget(title_label)

        # Сообщение
        label = Label(
            text=message,
            color=COLORS['DARK_TEXT'],
            font_size='18sp',
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=130
        )
        label.bind(size=label.setter('text_size'))
        content.add_widget(label)

        # Кнопка OK
        btn_layout = BoxLayout(size_hint_y=None, height=65, spacing=15)
        ok_btn = Button(
            text='OK',
            background_color=COLORS['DARK_BLUE'],
            color=(1, 1, 1, 1),
            font_size='19sp',
            bold=True,
            size_hint_x=0.7
        )
        btn_layout.add_widget(ok_btn)
        content.add_widget(btn_layout)

        popup = Popup(
            title='',
            content=content,
            size_hint=(0.92, 0.52),
            auto_dismiss=False,
            separator_height=0,
            background_color=(0.98, 0.99, 1.0, 0.95)
        )

        def close_popup(instance):
            popup.dismiss()
            if callback:
                callback()

        ok_btn.bind(on_press=close_popup)
        popup.open()
        return popup

    @staticmethod
    def create_confirmation_popup(title: str, message: str, yes_callback, no_callback=None) -> Popup:
        """Диалог подтверждения без эмодзи"""
        content = BoxLayout(orientation='vertical', padding=20, spacing=20)
        title_label = Label(
            text=f'[Подтверждение] {title}',
            color=COLORS['AMBER'],
            font_size='21sp',
            bold=True,
            size_hint_y=None,
            height=45,
            halign='center'
        )
        title_label.bind(size=title_label.setter('text_size'))
        content.add_widget(title_label)

        label = Label(
            text=message,
            color=COLORS['DARK_TEXT'],
            font_size='18sp',
            halign='center',
            size_hint_y=None,
            height=140
        )
        label.bind(size=label.setter('text_size'))
        content.add_widget(label)

        btn_layout = BoxLayout(size_hint_y=None, height=70, spacing=20)
        no_btn = Button(
            text='Отмена',
            background_color=COLORS['RED'],
            color=(1, 1, 1, 1),
            font_size='19sp',
            bold=True,
            size_hint_x=0.45
        )
        yes_btn = Button(
            text='Подтвердить',
            background_color=COLORS['GREEN'],
            color=(1, 1, 1, 1),
            font_size='19sp',
            bold=True,
            size_hint_x=0.45
        )

        popup = Popup(
            title='',
            content=content,
            size_hint=(0.92, 0.55),
            auto_dismiss=False,
            separator_height=0,
            background_color=(0.98, 0.99, 1.0, 0.95)
        )

        def on_no(instance):
            popup.dismiss()
            if no_callback:
                no_callback()

        def on_yes(instance):
            popup.dismiss()
            yes_callback()

        no_btn.bind(on_press=on_no)
        yes_btn.bind(on_press=on_yes)
        btn_layout.add_widget(no_btn)
        btn_layout.add_widget(yes_btn)
        content.add_widget(btn_layout)
        popup.open()
        return popup

    @staticmethod
    def create_table_header(labels: List[tuple], width: int = 1150) -> BoxLayout:
        """Создание заголовка таблицы с синим фоном"""
        header = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=54,
            padding=[12, 10],
            spacing=7,
            size_hint_x=None,
            width=width
        )
        with header.canvas.before:
            Color(0.10, 0.40, 0.80, 1)
            header.rect = Rectangle(pos=header.pos, size=header.size)

        def update_rect(instance, value):
            instance.rect.pos = instance.pos
            instance.rect.size = instance.size

        header.bind(pos=update_rect, size=update_rect)

        for text, width_ratio in labels:
            label = Label(
                text=text,
                font_size='17sp',
                bold=True,
                color=(1, 1, 1, 1),
                size_hint_x=width_ratio,
                halign='center',
                valign='middle'
            )
            label.bind(size=label.setter('text_size'))
            header.add_widget(label)

        return header

    @staticmethod
    def create_back_button(target_screen: str = 'profile', text: str = 'Назад') -> Button:
        """Кнопка «Назад» — единый стиль, фиксированная высота."""
        btn = Button(
            text=f'←  {text}',
            size_hint_y=None,
            height=BTN_BACK_H,
            background_color=COLORS['WHITE'],
            color=COLORS['DARK_BLUE'],
            font_size='17sp',
            bold=True,
        )
        btn.bind(on_press=lambda x: setattr(App.get_running_app().root, 'current', target_screen))
        return btn

    @staticmethod
    def create_menu_tile(icon: str, title: str, screen: str, color: tuple) -> Button:
        """Плитка меню: крупная, с иконкой сверху и подписью (как в банковских приложениях)."""
        btn = Button(
            text=f'{icon}\n{title}',
            size_hint_y=None,
            height=BTN_TILE_H,
            background_color=color,
            color=(1, 1, 1, 1),
            font_size='14sp',
            bold=True,
            halign='center',
            valign='middle',
        )
        btn.bind(size=btn.setter('text_size'))
        btn.bind(on_press=lambda x, s=screen: setattr(App.get_running_app().root, 'current', s))
        return btn

    @staticmethod
    def create_primary_button(text: str, height: int = BTN_ACTION_H) -> Button:
        """Основная действие — одна высота по всему приложению."""
        btn = Button(
            text=text,
            size_hint_y=None,
            height=height,
            background_color=COLORS['DARK_BLUE'],
            color=(1, 1, 1, 1),
            font_size='18sp',
            bold=True,
        )
        return btn

    @staticmethod
    def create_secondary_button(text: str, height: int = BTN_ACTION_H) -> Button:
        """Второстепенная кнопка (белая/светлая)."""
        btn = Button(
            text=text,
            size_hint_y=None,
            height=height,
            background_color=COLORS['LIGHT_GREY'],
            color=COLORS['DARK_TEXT'],
            font_size='17sp',
            bold=True,
        )
        return btn

# ============================================================================
# БАЗОВЫЙ КЛАСС ЭКРАНА (УСТРАНЕНИЕ ДУБЛИРОВАНИЯ)
# ============================================================================
class BaseScreen(Screen):
    """Базовый класс для всех экранов с общими методами"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_manager = App.get_running_app().data_manager
        self.business_logic = App.get_running_app().business_logic

    def show_popup(self, title: str, message: str, callback=None):
        UIComponents.create_popup(title, message, callback)

    def show_confirmation(self, title: str, message: str, yes_callback, no_callback=None):
        UIComponents.create_confirmation_popup(title, message, yes_callback, no_callback)

    def get_current_profile(self) -> Optional[str]:
        return App.get_running_app().current_profile

    def get_profile_data(self) -> Dict:
        profile_name = self.get_current_profile()
        if not profile_name:
            return {}
        return self.data_manager.get_profile_data(profile_name)

    def save_profile_data(self, data: Dict):
        profile_name = self.get_current_profile()
        if profile_name:
            self.data_manager.update_profile_data(profile_name, data)

# ============================================================================
# ЭКРАН: ВЫБОР ПРОФИЛЯ
# ============================================================================
class HomeScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=15, spacing=15)
        
        title = Label(
            text='Управление заказами',
            size_hint_y=0.12,
            font_size='26sp',
            bold=True,
            color=COLORS['DARK_BLUE'],
            halign='center'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)

        subtitle = Label(
            text='Товары, склад и заказы в одном приложении',
            size_hint_y=0.06,
            font_size='15sp',
            color=COLORS['MEDIUM_GREY'],
            halign='center',
        )
        subtitle.bind(size=subtitle.setter('text_size'))
        layout.add_widget(subtitle)

        scroll = ScrollView(size_hint_y=0.52)
        self.profiles_list = GridLayout(cols=1, spacing=12, size_hint_y=None)
        self.profiles_list.bind(minimum_height=self.profiles_list.setter('height'))
        scroll.add_widget(self.profiles_list)
        layout.add_widget(scroll)

        btn_create = UIComponents.create_primary_button('Создать новый профиль', height=56)
        btn_create.bind(on_press=self.show_create_profile)
        layout.add_widget(btn_create)

        btn_exit = Button(
            text='Выйти из приложения',
            size_hint_y=None,
            height=BTN_ACTION_H,
            background_color=COLORS['RED'],
            color=(1, 1, 1, 1),
            font_size='17sp',
            bold=True,
        )
        btn_exit.bind(on_press=lambda x: App.get_running_app().stop())
        layout.add_widget(btn_exit)

        self.add_widget(layout)
        self.load_profiles()

    def load_profiles(self):
        self.profiles_list.clear_widgets()
        profiles = self.data_manager.get_profiles()
        
        if not profiles:
            empty_label = Label(
                text='Нет профилей',
                size_hint_y=None,
                height=70,
                color=COLORS['MEDIUM_GREY'],
                font_size='21sp',
                bold=True,
                halign='center'
            )
            empty_label.bind(size=empty_label.setter('text_size'))
            self.profiles_list.add_widget(empty_label)
            
            hint_label = Label(
                text='Нажмите "Создать новый профиль" чтобы начать',
                size_hint_y=None,
                height=50,
                color=COLORS['LIGHT_GREY'],
                font_size='15sp',
                halign='center',
                italic=True
            )
            hint_label.bind(size=hint_label.setter('text_size'))
            self.profiles_list.add_widget(hint_label)
            return

        for profile_name in sorted(profiles.keys()):
            profile_container = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=64,
                spacing=10
            )
            btn = Button(
                text=profile_name,
                size_hint_x=0.82,
                background_color=COLORS['WHITE'],
                color=COLORS['DARK_BLUE'],
                font_size='18sp',
                bold=True,
            )
            btn.bind(on_press=lambda instance, name=profile_name: self.select_profile(name))
            del_btn = Button(
                text='Удалить',
                size_hint_x=0.18,
                size_hint_y=None,
                height=44,
                background_color=COLORS['RED'],
                color=(1, 1, 1, 1),
                font_size='14sp',
                bold=True,
            )
            del_btn.bind(on_press=lambda instance, name=profile_name: self.confirm_delete_profile(name))
            profile_container.add_widget(btn)
            profile_container.add_widget(del_btn)
            self.profiles_list.add_widget(profile_container)

    def select_profile(self, profile_name):
        app = App.get_running_app()
        app.current_profile = profile_name
        app.profile_data = self.data_manager.get_profile_data(profile_name)
        self.manager.current = 'profile'

    def confirm_delete_profile(self, profile_name):
        self.show_confirmation(
            title='Удаление профиля',
            message=f'Вы уверены, что хотите удалить профиль «{profile_name}»?\n'
                    f'Все данные (товары, склад и история заказов) будут безвозвратно удалены.',
            yes_callback=lambda: self.delete_profile(profile_name)
        )

    def delete_profile(self, profile_name):
        profiles = self.data_manager.get_profiles()
        if profile_name not in profiles:
            self.show_popup('Ошибка', 'Профиль не найден')
            return
        
        del profiles[profile_name]
        self.data_manager.save_profiles(profiles)
        
        app = App.get_running_app()
        if app.current_profile == profile_name:
            app.current_profile = None
            app.profile_data = {}
        
        self.show_popup(
            'Успех',
            f'Профиль «{profile_name}» успешно удалён со всеми данными!',
            callback=self.load_profiles
        )

    def show_create_profile(self, instance):
        content = BoxLayout(orientation='vertical', padding=22, spacing=20)
        
        title_label = Label(
            text='Создание профиля',
            color=COLORS['DARK_BLUE'],
            font_size='23sp',
            bold=True,
            size_hint_y=None,
            height=48,
            halign='center'
        )
        title_label.bind(size=title_label.setter('text_size'))
        content.add_widget(title_label)

        input_field = TextInput(
            hint_text='Введите имя профиля (например: "Мой магазин")',
            multiline=False,
            font_size='19sp',
            size_hint_y=None,
            height=68,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[16, 14],
            cursor_color=COLORS['DARK_BLUE']
        )
        content.add_widget(input_field)

        hint_label = Label(
            text='Имя профиля будет отображаться в заголовке приложения',
            color=COLORS['MEDIUM_GREY'],
            font_size='15sp',
            size_hint_y=None,
            height=48,
            halign='center',
            italic=True
        )
        hint_label.bind(size=hint_label.setter('text_size'))
        content.add_widget(hint_label)

        buttons = BoxLayout(spacing=14, size_hint_y=None, height=BTN_ACTION_H + 4)
        cancel_btn = Button(
            text='Отмена',
            size_hint_x=0.45,
            size_hint_y=None,
            height=BTN_ACTION_H,
            background_color=COLORS['MEDIUM_GREY'],
            color=(1, 1, 1, 1),
            font_size='17sp',
            bold=True,
        )
        ok_btn = Button(
            text='Создать',
            size_hint_x=0.55,
            size_hint_y=None,
            height=BTN_ACTION_H,
            background_color=COLORS['GREEN'],
            color=(1, 1, 1, 1),
            font_size='17sp',
            bold=True,
        )

        popup = Popup(
            title='',
            content=content,
            size_hint=(0.92, 0.48),
            separator_height=0,
            background_color=(0.98, 0.99, 1.0, 0.95)
        )

        def create(instance):
            name = input_field.text.strip()
            if not name:
                popup.dismiss()
                self.show_popup('Ошибка', 'Имя профиля не может быть пустым')
                return
            
            profiles = self.data_manager.get_profiles()
            if name in profiles:
                popup.dismiss()
                self.show_popup('Ошибка', f'Профиль «{name}» уже существует')
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
            self.show_popup('Успех', f'Профиль «{name}» успешно создан!')

        cancel_btn.bind(on_press=popup.dismiss)
        ok_btn.bind(on_press=create)
        buttons.add_widget(cancel_btn)
        buttons.add_widget(ok_btn)
        content.add_widget(buttons)
        popup.open()

# ============================================================================
# ЭКРАН: ПАНЕЛЬ ПРОФИЛЯ
# ============================================================================
class ProfileScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=12, spacing=12)
        
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=BTN_BACK_H + 14, spacing=8)
        back_btn = UIComponents.create_back_button('home')
        header.add_widget(back_btn)
        self.title_label = Label(
            text='',
            size_hint_x=0.7,
            font_size='20sp',
            bold=True,
            color=COLORS['DARK_BLUE'],
            halign='left',
            valign='middle'
        )
        self.title_label.bind(size=self.title_label.setter('text_size'))
        header.add_widget(self.title_label)
        layout.add_widget(header)

        grid = GridLayout(cols=2, spacing=12, size_hint_y=None, padding=[0, 8])
        grid.bind(minimum_height=grid.setter('height'))
        tiles_config = [
            ("📦", "Каталог\nтоваров", "products", COLORS['TILE_BLUE']),
            ("➕", "Добавить\nтовар", "add_product", COLORS['TILE_GREEN']),
            ("📥", "Склад", "warehouse", COLORS['TILE_TEAL']),
            ("📝", "Создать\nзаказ", "create_order", COLORS['TILE_VIOLET']),
            ("📊", "Анализ\nпродаж", "sales_analysis", COLORS['TILE_AMBER']),
            ("📋", "История\nзаказов", "order_history", COLORS['TILE_PINK']),
        ]
        for icon, title, screen, color in tiles_config:
            btn = UIComponents.create_menu_tile(icon, title, screen, color)
            grid.add_widget(btn)
        logout_btn = UIComponents.create_menu_tile("🚪", "Выход из\nпрофиля", "home", COLORS['RED'])
        grid.add_widget(logout_btn)
        scroll_grid = ScrollView(size_hint_y=0.82)
        scroll_grid.add_widget(grid)
        layout.add_widget(scroll_grid)
        self.add_widget(layout)

    def on_enter(self):
        profile_name = self.get_current_profile()
        self.title_label.text = f'Профиль: {profile_name}' if profile_name else 'Профиль не выбран'

# ============================================================================
# ЭКРАН: КАТАЛОГ ТОВАРОВ
# ============================================================================
class ProductsScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=12, spacing=12)
        layout.add_widget(UIComponents.create_back_button('profile'))
        
        title = Label(
            text='Каталог товаров',
            size_hint_y=0.09,
            font_size='25sp',
            bold=True,
            color=COLORS['DARK_BLUE'],
            halign='center'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)

        stats_hint = Label(
            text='Нажмите "Редактировать" для изменения характеристик товара',
            size_hint_y=0.06,
            font_size='16sp',
            color=COLORS['MEDIUM_GREY'],
            halign='center',
            italic=True
        )
        stats_hint.bind(size=stats_hint.setter('text_size'))
        layout.add_widget(stats_hint)

        self.scroll = ScrollView(size_hint_y=0.72)
        self.products_list = GridLayout(cols=1, spacing=12, size_hint_y=None)
        self.products_list.bind(minimum_height=self.products_list.setter('height'))
        self.scroll.add_widget(self.products_list)
        layout.add_widget(self.scroll)
        
        self.add_widget(layout)

    def on_enter(self):
        self.load_products()

    def load_products(self):
        self.products_list.clear_widgets()
        profile_data = self.get_profile_data()
        products = profile_data.get("products", [])
        
        if not products:
            empty_label = Label(
                text='Нет товаров в каталоге',
                size_hint_y=None,
                height=70,
                color=COLORS['MEDIUM_GREY'],
                font_size='21sp',
                bold=True,
                halign='center'
            )
            empty_label.bind(size=empty_label.setter('text_size'))
            self.products_list.add_widget(empty_label)
            
            hint_label = Label(
                text='Нажмите "Добавить товар" в главном меню чтобы добавить товар',
                size_hint_y=None,
                height=50,
                color=COLORS['LIGHT_GREY'],
                font_size='15sp',
                halign='center',
                italic=True
            )
            hint_label.bind(size=hint_label.setter('text_size'))
            self.products_list.add_widget(hint_label)
            return

        for product in sorted(products, key=lambda x: x["name"]):
            card = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=108,
                padding=[10, 6],
                spacing=10
            )
            
            info_layout = BoxLayout(orientation='vertical', size_hint_x=0.85, spacing=4)
            name_label = Label(
                text=f'Название: {product["name"]}',
                font_size='20sp',
                bold=True,
                color=COLORS['DARK_BLUE'],
                size_hint_y=None,
                height=34
            )
            price_label = Label(
                text=f'Цена: {product["cost_price"]:.2f} ₽/кг',
                font_size='17sp',
                color=COLORS['DARK_TEXT'],
                size_hint_y=None,
                height=30
            )
            profit_label = Label(
                text=f'Прибыль: {product["profit"]:.2f} ₽ ({product["percent_profit"]:.1f}%)',
                font_size='17sp',
                color=COLORS['GREEN'],
                size_hint_y=None,
                height=30
            )
            info_layout.add_widget(name_label)
            info_layout.add_widget(price_label)
            info_layout.add_widget(profit_label)

            edit_btn = Button(
                text='Редактировать',
                size_hint_x=0.15,
                size_hint_y=None,
                height=92,
                background_color=COLORS['AMBER'],
                color=(1, 1, 1, 1),
                font_size='14sp',
                bold=True
            )
            edit_btn.bind(on_press=lambda instance, p=product: self.edit_product(p))
            
            card.add_widget(info_layout)
            card.add_widget(edit_btn)
            self.products_list.add_widget(card)

    def edit_product(self, product):
        app = App.get_running_app()
        app.product_to_edit = product
        self.manager.current = 'edit_product'

# ============================================================================
# ЭКРАН: ДОБАВЛЕНИЕ ТОВАРА
# ============================================================================
class AddProductScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=15, spacing=15)
        layout.add_widget(UIComponents.create_back_button('profile'))
        
        title = Label(
            text='Добавление товара',
            size_hint_y=0.09,
            font_size='25sp',
            bold=True,
            color=COLORS['GREEN'],
            halign='center'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)

        form_layout = GridLayout(cols=1, spacing=15, padding=[0, 10, 0, 0])
        
        form_layout.add_widget(Label(
            text='Название товара:',
            color=COLORS['DARK_BLUE'],
            font_size='18sp',
            bold=True,
            size_hint_y=None,
            height=38
        ))
        
        self.name_input = TextInput(
            multiline=False,
            font_size='19sp',
            height=58,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[14, 12],
            cursor_color=COLORS['DARK_BLUE']
        )
        form_layout.add_widget(self.name_input)

        form_layout.add_widget(Label(
            text='Стоимость за кг (₽):',
            color=COLORS['DARK_BLUE'],
            font_size='18sp',
            bold=True,
            size_hint_y=None,
            height=38
        ))
        
        self.cost_input = TextInput(
            text='0.00',
            multiline=False,
            font_size='19sp',
            height=58,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[14, 12],
            cursor_color=COLORS['DARK_BLUE']
        )
        self.cost_input.bind(text=self.update_calculations)
        form_layout.add_widget(self.cost_input)

        form_layout.add_widget(Label(
            text='Прибыль (₽):',
            color=COLORS['DARK_BLUE'],
            font_size='18sp',
            bold=True,
            size_hint_y=None,
            height=38
        ))
        
        self.profit_input = TextInput(
            text='0.00',
            multiline=False,
            font_size='19sp',
            height=58,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[14, 12],
            cursor_color=COLORS['DARK_BLUE']
        )
        self.profit_input.bind(text=self.update_calculations)
        form_layout.add_widget(self.profit_input)

        calc_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=125, padding=[14, 12])
        
        self.expenses_label = Label(
            text='Затраты: 0.00 ₽',
            color=COLORS['ORANGE'],
            font_size='18sp',
            bold=True,
            size_hint_y=None,
            height=40
        )
        
        self.percent_label = Label(
            text='%Затрат: 0.00% | %Прибыли: 0.00%',
            color=COLORS['DARK_BLUE'],
            font_size='17sp',
            bold=True,
            size_hint_y=None,
            height=40
        )
        
        formula_label = Label(
            text='Формула: %Затрат = (Затраты / (Затраты + Прибыль)) × 100%',
            color=COLORS['MEDIUM_GREY'],
            font_size='15sp',
            italic=True,
            size_hint_y=None,
            height=36
        )
        
        calc_layout.add_widget(self.expenses_label)
        calc_layout.add_widget(self.percent_label)
        calc_layout.add_widget(formula_label)
        
        form_layout.add_widget(calc_layout)
        layout.add_widget(form_layout)

        save_btn = Button(
            text='Сохранить товар',
            size_hint_y=0.14,
            background_color=COLORS['GREEN'],
            color=(1, 1, 1, 1),
            font_size='22sp',
            bold=True
        )
        save_btn.bind(on_press=self.save_product)
        layout.add_widget(save_btn)
        
        self.add_widget(layout)

    def on_enter(self):
        self.name_input.text = ''
        self.cost_input.text = '0.00'
        self.profit_input.text = '0.00'
        self.expenses_label.text = 'Затраты: 0.00 ₽'
        self.percent_label.text = '%Затрат: 0.00% | %Прибыли: 0.00%'

    def update_calculations(self, instance, value):
        try:
            cost = float(self.cost_input.text or '0')
            profit = float(self.profit_input.text or '0')
            if cost > 0 and profit >= 0 and profit <= cost:
                expenses = cost - profit
                percent_exp = self.business_logic.calculate_percent_expenses(cost, profit)
                percent_profit = self.business_logic.calculate_percent_profit(cost, profit)
                self.expenses_label.text = f'Затраты: {expenses:.2f} ₽'
                self.percent_label.text = f'%Затрат: {percent_exp:.2f}% | %Прибыли: {percent_profit:.2f}%'
        except ValueError:
            pass

    def save_product(self, instance):
        profile_data = self.get_profile_data()
        
        name, error = Validators.validate_non_empty(self.name_input.text, "Название товара")
        if error:
            self.show_popup('Ошибка', error)
            return
        
        cost, error = Validators.validate_positive_float(self.cost_input.text, "Стоимость")
        if error:
            self.show_popup('Ошибка', error)
            return
        
        profit, error = Validators.validate_positive_float(self.profit_input.text or '0', "Прибыль")
        if error:
            self.show_popup('Ошибка', error)
            return
        
        if profit > cost:
            self.show_popup('Ошибка', 'Прибыль не может превышать стоимость')
            return
        
        existing = [p["name"].lower() for p in profile_data.get("products", [])]
        if name.lower() in existing:
            self.show_popup('Ошибка', f'Товар «{name}» уже существует')
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
        
        # Сброс формы
        self.name_input.text = ''
        self.cost_input.text = '0.00'
        self.profit_input.text = '0.00'
        self.expenses_label.text = 'Затраты: 0.00 ₽'
        self.percent_label.text = '%Затрат: 0.00% | %Прибыли: 0.00%'
        
        self.show_popup('Успех', f'Товар «{name}» успешно добавлен!',
                        callback=lambda: setattr(self.manager, 'current', 'profile'))

# ============================================================================
# ЭКРАН: РЕДАКТИРОВАНИЕ ТОВАРА
# ============================================================================
class EditProductScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=15, spacing=15)
        layout.add_widget(UIComponents.create_back_button('products'))
        
        self.title_label = Label(
            text='Редактирование товара',
            size_hint_y=0.09,
            font_size='25sp',
            bold=True,
            color=COLORS['AMBER'],
            halign='center'
        )
        self.title_label.bind(size=self.title_label.setter('text_size'))
        layout.add_widget(self.title_label)

        form_layout = GridLayout(cols=1, spacing=15, padding=[0, 10, 0, 0])
        
        form_layout.add_widget(Label(
            text='Название товара:',
            color=COLORS['DARK_BLUE'],
            font_size='18sp',
            bold=True,
            size_hint_y=None,
            height=38
        ))
        
        self.name_input = TextInput(
            multiline=False,
            font_size='19sp',
            height=58,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[14, 12],
            cursor_color=COLORS['DARK_BLUE']
        )
        form_layout.add_widget(self.name_input)

        form_layout.add_widget(Label(
            text='Стоимость за кг (₽):',
            color=COLORS['DARK_BLUE'],
            font_size='18sp',
            bold=True,
            size_hint_y=None,
            height=38
        ))
        
        self.cost_input = TextInput(
            text='0.00',
            multiline=False,
            font_size='19sp',
            height=58,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[14, 12],
            cursor_color=COLORS['DARK_BLUE']
        )
        self.cost_input.bind(text=self.update_calculations)
        form_layout.add_widget(self.cost_input)

        form_layout.add_widget(Label(
            text='Прибыль (₽):',
            color=COLORS['DARK_BLUE'],
            font_size='18sp',
            bold=True,
            size_hint_y=None,
            height=38
        ))
        
        self.profit_input = TextInput(
            text='0.00',
            multiline=False,
            font_size='19sp',
            height=58,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[14, 12],
            cursor_color=COLORS['DARK_BLUE']
        )
        self.profit_input.bind(text=self.update_calculations)
        form_layout.add_widget(self.profit_input)

        calc_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=125, padding=[14, 12])
        
        self.expenses_label = Label(
            text='Затраты: 0.00 ₽',
            color=COLORS['ORANGE'],
            font_size='18sp',
            bold=True,
            size_hint_y=None,
            height=40
        )
        
        self.percent_label = Label(
            text='%Затрат: 0.00% | %Прибыли: 0.00%',
            color=COLORS['DARK_BLUE'],
            font_size='17sp',
            bold=True,
            size_hint_y=None,
            height=40
        )
        
        formula_label = Label(
            text='Формула: %Затрат = (Затраты / (Затраты + Прибыль)) × 100%',
            color=COLORS['MEDIUM_GREY'],
            font_size='15sp',
            italic=True,
            size_hint_y=None,
            height=36
        )
        
        calc_layout.add_widget(self.expenses_label)
        calc_layout.add_widget(self.percent_label)
        calc_layout.add_widget(formula_label)
        
        form_layout.add_widget(calc_layout)
        layout.add_widget(form_layout)

        btn_layout = BoxLayout(spacing=16, size_hint_y=None, height=78)
        
        delete_btn = Button(
            text='Удалить',
            background_color=COLORS['RED'],
            color=(1, 1, 1, 1),
            font_size='19sp',
            bold=True,
            size_hint_x=0.45
        )
        
        save_btn = Button(
            text='Сохранить',
            background_color=COLORS['GREEN'],
            color=(1, 1, 1, 1),
            font_size='19sp',
            bold=True,
            size_hint_x=0.45
        )
        
        delete_btn.bind(on_press=self.confirm_delete)
        save_btn.bind(on_press=self.save_product)
        
        btn_layout.add_widget(delete_btn)
        btn_layout.add_widget(save_btn)
        layout.add_widget(btn_layout)
        
        self.add_widget(layout)

    def on_enter(self):
        app = App.get_running_app()
        product = app.product_to_edit
        self.title_label.text = f'Редактирование: {product["name"]}'
        self.name_input.text = product["name"]
        self.cost_input.text = f'{product["cost_price"]:.2f}'
        self.profit_input.text = f'{product["profit"]:.2f}'
        self.update_calculations(None, self.cost_input.text)

    def update_calculations(self, instance, value):
        try:
            cost = float(self.cost_input.text or '0')
            profit = float(self.profit_input.text or '0')
            if cost > 0 and profit >= 0 and profit <= cost:
                expenses = cost - profit
                percent_exp = self.business_logic.calculate_percent_expenses(cost, profit)
                percent_profit = self.business_logic.calculate_percent_profit(cost, profit)
                self.expenses_label.text = f'Затраты: {expenses:.2f} ₽'
                self.percent_label.text = f'%Затрат: {percent_exp:.2f}% | %Прибыли: {percent_profit:.2f}%'
        except ValueError:
            pass

    def confirm_delete(self, instance):
        product_name = self.name_input.text.strip()
        self.show_confirmation(
            title='Удаление товара',
            message=f'Вы уверены, что хотите удалить товар «{product_name}»?\n'
                    f'Все данные о товаре (включая остатки на складе) будут удалены!',
            yes_callback=self.delete_product
        )

    def delete_product(self):
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
            'Успех',
            f'Товар «{product_name}» удален!',
            callback=lambda: setattr(self.manager, 'current', 'products')
        )

    def save_product(self, instance):
        app = App.get_running_app()
        profile_data = self.get_profile_data()
        old_name = app.product_to_edit["name"]
        
        new_name, error = Validators.validate_non_empty(self.name_input.text, "Название товара")
        if error:
            self.show_popup('Ошибка', error)
            return
        
        cost, error = Validators.validate_positive_float(self.cost_input.text, "Стоимость")
        if error:
            self.show_popup('Ошибка', error)
            return
        
        profit, error = Validators.validate_positive_float(self.profit_input.text or '0', "Прибыль")
        if error:
            self.show_popup('Ошибка', error)
            return
        
        if profit > cost:
            self.show_popup('Ошибка', 'Прибыль не может превышать стоимость')
            return
        
        existing = [p["name"].lower() for p in profile_data.get("products", [])
                    if p["name"].lower() != old_name.lower()]
        if new_name.lower() in existing:
            self.show_popup('Ошибка', f'Товар «{new_name}» уже существует')
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
            'Успех',
            f'Товар «{new_name}» успешно обновлен!',
            callback=lambda: setattr(self.manager, 'current', 'products')
        )

# ============================================================================
# ЭКРАН: СКЛАД
# ============================================================================
class WarehouseScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=12, spacing=12)
        layout.add_widget(UIComponents.create_back_button('profile'))
        
        self.stats_label = Label(
            text='Общая стоимость: 0.00 ₽\nОбщий остаток: 0.00 кг',
            size_hint_y=0.15,
            font_size='18sp',
            halign='center',
            color=COLORS['DARK_TEXT']
        )
        self.stats_label.bind(size=self.stats_label.setter('text_size'))
        layout.add_widget(self.stats_label)

        scroll = ScrollView(size_hint_y=0.62)
        self.warehouse_list = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.warehouse_list.bind(minimum_height=self.warehouse_list.setter('height'))
        scroll.add_widget(self.warehouse_list)
        layout.add_widget(scroll)

        btn_layout = BoxLayout(orientation='horizontal', size_hint_y=0.08, spacing=10)
        
        add_btn = Button(
            text='Пополнить',
            background_color=COLORS['TEAL'],
            color=(1, 1, 1, 1),
            font_size='17sp',
            bold=True
        )
        
        edit_btn = Button(
            text='Скорректировать',
            background_color=COLORS['AMBER'],
            color=(1, 1, 1, 1),
            font_size='17sp',
            bold=True
        )
        
        history_btn = Button(
            text='История',
            background_color=COLORS['PINK'],
            color=(1, 1, 1, 1),
            font_size='17sp',
            bold=True
        )
        
        add_btn.bind(on_press=self.go_to_add_stock)
        edit_btn.bind(on_press=self.open_edit_warehouse_dialog)
        history_btn.bind(on_press=self.go_to_stock_history)
        
        btn_layout.add_widget(add_btn)
        btn_layout.add_widget(edit_btn)
        btn_layout.add_widget(history_btn)
        layout.add_widget(btn_layout)
        
        self.add_widget(layout)

    def on_enter(self):
        self.load_warehouse()

    def load_warehouse(self):
        profile_data = self.get_profile_data()
        
        total_value = sum(data["total_value"] for data in profile_data["stock"].values())
        total_qty = sum(data["current_quantity"] for data in profile_data["stock"].values())
        total_products = len(profile_data.get("products", []))
        products_with_stock = sum(1 for data in profile_data["stock"].values() if data["current_quantity"] > 0)
        
        self.stats_label.text = (
            f'Всего товаров: {total_products}\n'
            f'С остатком: {products_with_stock}\n'
            f'Общий остаток: {total_qty:.2f} кг\n'
            f'Общая стоимость: {total_value:.2f} ₽'
        )
        
        self.warehouse_list.clear_widgets()
        products = profile_data.get("products", [])
        
        if not products:
            empty_label = Label(
                text='Нет товаров в каталоге',
                size_hint_y=None,
                height=60,
                color=COLORS['MEDIUM_GREY'],
                font_size='21sp',
                bold=True,
                halign='center'
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
                height=92,
                padding=[8, 5],
                spacing=8
            )
            
            info_layout = BoxLayout(
                orientation='vertical',
                size_hint_x=0.85,
                spacing=2
            )
            
            name_label = Label(
                text=product_name,
                font_size='18sp',
                bold=True,
                color=COLORS['DARK_TEXT'],
                size_hint_y=None,
                height=28
            )
            
            qty_label = Label(
                text=f'Остаток: {qty:.2f} кг',
                font_size='16sp',
                color=COLORS['GREEN'] if qty > 0 else COLORS['RED'],
                size_hint_y=None,
                height=26
            )
            
            price_label = Label(
                text=f'Ср. цена: {avg_price:.2f} ₽/кг',
                font_size='16sp',
                color=COLORS['DARK_TEXT'],
                size_hint_y=None,
                height=26
            )
            
            info_layout.add_widget(name_label)
            info_layout.add_widget(qty_label)
            info_layout.add_widget(price_label)

            edit_btn = Button(
                text='Изменить',
                size_hint_x=0.15,
                size_hint_y=None,
                height=72,
                background_color=COLORS['AMBER'],
                color=(1, 1, 1, 1),
                font_size='14sp',
                bold=True
            )
            edit_btn.bind(on_press=lambda instance, p=product_name: self.edit_warehouse_item(p))
            
            card.add_widget(info_layout)
            card.add_widget(edit_btn)
            self.warehouse_list.add_widget(card)

    def go_to_add_stock(self, instance):
        self.manager.current = 'add_stock'

    def open_edit_warehouse_dialog(self, instance):
        self.edit_warehouse_item(None)

    def go_to_stock_history(self, instance):
        self.manager.current = 'stock_history'

    def edit_warehouse_item(self, product_name):
        profile_data = self.get_profile_data()
        
        if product_name is None:
            # Корректировка любого товара — показываем выбор
            if not profile_data.get("products"):
                self.show_popup('Ошибка', 'Нет товаров в каталоге')
                return
            
            content = BoxLayout(orientation='vertical', padding=16, spacing=12)
            
            title_label = Label(
                text='Выберите товар для корректировки',
                color=COLORS['DARK_TEXT'],
                font_size='19sp',
                bold=True,
                size_hint_y=None,
                height=42
            )
            content.add_widget(title_label)
            
            scroll = ScrollView(size_hint_y=0.7)
            products_list = GridLayout(cols=1, spacing=8, size_hint_y=None)
            products_list.bind(minimum_height=products_list.setter('height'))
            
            for product in sorted(profile_data["products"], key=lambda x: x["name"]):
                btn = Button(
                    text=product["name"],
                    size_hint_y=None,
                    height=48,
                    background_color=COLORS['WHITE'],
                    color=COLORS['DARK_TEXT'],
                    font_size='17sp'
                )
                btn.bind(on_press=lambda instance, p=product["name"]: self._open_edit_dialog(p, content.parent))
                products_list.add_widget(btn)
            
            scroll.add_widget(products_list)
            content.add_widget(scroll)
            
            popup = Popup(
                title='',
                content=content,
                size_hint=(0.92, 0.85),
                separator_height=0,
                background_color=(0.98, 0.99, 1.0, 0.95)
            )
            popup.open()
            return
        
        # Корректировка конкретного товара
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
        
        content = BoxLayout(orientation='vertical', padding=16, spacing=16)
        
        title_label = Label(
            text=f'Редактирование: {product_name}',
            color=COLORS['DARK_TEXT'],
            font_size='19sp',
            bold=True,
            size_hint_y=None,
            height=42
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
                text=f"Стоимость продажи: {product_info['cost_price']:.2f} ₽/кг\n"
                     f"Прибыль: {product_info['profit']:.2f} ₽ ({percent_profit:.1f}%)",
                color=COLORS['MEDIUM_GREY'],
                font_size='15sp',
                size_hint_y=None,
                height=62
            )
            content.add_widget(price_info)
        
        qty_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=82)
        qty_layout.add_widget(Label(
            text='Остаток (кг):',
            color=COLORS['DARK_TEXT'],
            font_size='17sp',
            bold=True,
            size_hint_y=None,
            height=32
        ))
        
        self.qty_input = TextInput(
            text=f'{current_qty:.2f}',
            multiline=False,
            font_size='19sp',
            height=50,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[10, 10],
            cursor_color=COLORS['DARK_BLUE']
        )
        qty_layout.add_widget(self.qty_input)
        content.add_widget(qty_layout)
        
        price_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=82)
        price_layout.add_widget(Label(
            text='Средняя цена закупки (₽/кг):',
            color=COLORS['DARK_TEXT'],
            font_size='17sp',
            bold=True,
            size_hint_y=None,
            height=32
        ))
        
        self.price_input = TextInput(
            text=f'{avg_price:.2f}',
            multiline=False,
            font_size='19sp',
            height=50,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[10, 10],
            cursor_color=COLORS['DARK_BLUE']
        )
        price_layout.add_widget(self.price_input)
        content.add_widget(price_layout)
        
        calc_label = Label(
            text=f'Текущая стоимость остатка: {current_value:.2f} ₽',
            color=COLORS['MEDIUM_GREY'],
            font_size='15sp',
            size_hint_y=None,
            height=38
        )
        content.add_widget(calc_label)
        
        buttons_layout = BoxLayout(spacing=16, size_hint_y=None, height=72)
        
        cancel_btn = Button(
            text='Отмена',
            background_color=COLORS['RED'],
            color=(1, 1, 1, 1),
            font_size='18sp',
            bold=True
        )
        
        save_btn = Button(
            text='Сохранить',
            background_color=COLORS['GREEN'],
            color=(1, 1, 1, 1),
            font_size='18sp',
            bold=True
        )
        
        popup = Popup(
            title='',
            content=content,
            size_hint=(0.92, 0.88),
            separator_height=0,
            background_color=(0.98, 0.99, 1.0, 0.95)
        )
        
        def cancel(instance):
            popup.dismiss()
        
        def save(instance):
            try:
                new_quantity = float(self.qty_input.text.replace(',', '.'))
                new_avg_price = float(self.price_input.text.replace(',', '.'))
                
                if new_quantity < 0:
                    self.show_popup('Ошибка', 'Остаток не может быть отрицательным!')
                    return
                
                if new_avg_price < 0:
                    self.show_popup('Ошибка', 'Цена закупки не может быть отрицательной!')
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
                self.show_popup('Успех', f'Товар «{product_name}» успешно скорректирован!')
            
            except ValueError:
                self.show_popup('Ошибка', 'Введите корректные числовые значения!')
        
        cancel_btn.bind(on_press=cancel)
        save_btn.bind(on_press=save)
        
        buttons_layout.add_widget(cancel_btn)
        buttons_layout.add_widget(save_btn)
        content.add_widget(buttons_layout)
        popup.open()

    def _open_edit_dialog(self, product_name, popup):
        popup.dismiss()
        self.edit_warehouse_item(product_name)

# ============================================================================
# ЭКРАН: ДОБАВЛЕНИЕ НА СКЛАД
# ============================================================================
class AddStockScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=15, spacing=15)
        layout.add_widget(UIComponents.create_back_button('warehouse', 'Назад к складу'))
        
        title = Label(
            text='Пополнение склада',
            size_hint_y=0.1,
            font_size='23sp',
            bold=True,
            color=COLORS['TEAL'],
            halign='center'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)

        form_layout = GridLayout(cols=1, spacing=13, padding=[0, 10, 0, 0])
        
        form_layout.add_widget(Label(
            text='Товар:',
            color=COLORS['DARK_TEXT'],
            font_size='17sp',
            bold=True,
            size_hint_y=None,
            height=32
        ))
        
        self.product_btn = Button(
            text='Выберите товар',
            background_color=COLORS['LIGHT_BG'],
            color=COLORS['DARK_TEXT'],
            font_size='17sp',
            size_hint_y=None,
            height=52
        )
        self.product_btn.bind(on_press=self.show_product_dropdown)
        form_layout.add_widget(self.product_btn)

        form_layout.add_widget(Label(
            text='Количество (кг):',
            color=COLORS['DARK_TEXT'],
            font_size='17sp',
            bold=True,
            size_hint_y=None,
            height=32
        ))
        
        self.qty_input = TextInput(
            text='1.0',
            multiline=False,
            font_size='19sp',
            height=52,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[10, 10],
            cursor_color=COLORS['DARK_BLUE']
        )
        form_layout.add_widget(self.qty_input)

        form_layout.add_widget(Label(
            text='Цена закупки за кг (₽):',
            color=COLORS['DARK_TEXT'],
            font_size='17sp',
            bold=True,
            size_hint_y=None,
            height=32
        ))
        
        self.price_input = TextInput(
            text='100.00',
            multiline=False,
            font_size='19sp',
            height=52,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[10, 10],
            cursor_color=COLORS['DARK_BLUE']
        )
        form_layout.add_widget(self.price_input)

        info_label = Label(
            text='Цена закупки используется для расчёта стоимости запасов',
            color=COLORS['MEDIUM_GREY'],
            font_size='15sp',
            italic=True,
            size_hint_y=None,
            height=42
        )
        form_layout.add_widget(info_label)
        
        layout.add_widget(form_layout)

        save_btn = Button(
            text='Добавить на склад',
            size_hint_y=0.14,
            background_color=COLORS['TEAL'],
            color=(1, 1, 1, 1),
            font_size='21sp',
            bold=True
        )
        save_btn.bind(on_press=self.save_to_stock)
        layout.add_widget(save_btn)
        
        self.add_widget(layout)

    def on_enter(self):
        self.product_btn.text = 'Выберите товар'
        self.qty_input.text = '1.0'
        self.price_input.text = '100.00'

    def show_product_dropdown(self, instance):
        profile_data = self.get_profile_data()
        products = [p["name"] for p in profile_data.get("products", [])]
        
        if not products:
            self.show_popup('Ошибка', 'Нет товаров в каталоге')
            return
        
        dropdown = DropDown()
        for product in products:
            btn = Button(
                text=product,
                size_hint_y=None,
                height=42,
                background_color=COLORS['WHITE'],
                color=COLORS['DARK_TEXT'],
                font_size='17sp'
            )
            btn.bind(on_release=lambda btn, p=product: self.select_product(p, dropdown))
            dropdown.add_widget(btn)
        
        dropdown.open(self.product_btn)

    def select_product(self, product_name, dropdown):
        self.product_btn.text = product_name
        dropdown.dismiss()

    def save_to_stock(self, instance):
        product_name = self.product_btn.text
        if product_name == 'Выберите товар':
            self.show_popup('Ошибка', 'Выберите товар!')
            return
        
        qty, error = Validators.validate_positive_float(self.qty_input.text, "Количество")
        if error:
            self.show_popup('Ошибка', error)
            return
        
        price, error = Validators.validate_positive_float(self.price_input.text, "Цена закупки")
        if error:
            self.show_popup('Ошибка', error)
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
            'Успех',
            f'На склад добавлено {qty:.2f} кг товара «{product_name}»\n'
            f'Цена закупки: {price:.2f} ₽/кг',
            callback=lambda: setattr(self.manager, 'current', 'warehouse')
        )

# ============================================================================
# ЭКРАН: СОЗДАНИЕ ЗАКАЗА
# ============================================================================
class CreateOrderScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.order_items = []
        self.delivery_enabled = True
        self.current_order_number = 1
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=12, spacing=12)
        layout.add_widget(UIComponents.create_back_button('profile'))
        
        self.title_label = Label(
            text='Заказ №1',
            size_hint_y=0.08,
            font_size='23sp',
            bold=True,
            color=COLORS['PURPLE'],
            halign='center'
        )
        layout.add_widget(self.title_label)

        product_layout = BoxLayout(orientation='vertical', size_hint_y=0.15)
        product_layout.add_widget(Label(
            text='Товар:',
            color=COLORS['DARK_TEXT'],
            font_size='17sp',
            size_hint_y=None,
            height=32
        ))
        
        self.product_btn = Button(
            text='Выберите товар',
            background_color=COLORS['LIGHT_BG'],
            color=COLORS['DARK_TEXT'],
            font_size='17sp',
            size_hint_y=None,
            height=52
        )
        self.product_btn.bind(on_press=self.show_product_dropdown)
        product_layout.add_widget(self.product_btn)
        layout.add_widget(product_layout)

        qty_layout = BoxLayout(orientation='vertical', size_hint_y=0.12)
        qty_layout.add_widget(Label(
            text='Количество (кг):',
            color=COLORS['DARK_TEXT'],
            font_size='17sp',
            size_hint_y=None,
            height=32
        ))
        
        self.qty_input = TextInput(
            text='1.0',
            multiline=False,
            font_size='19sp',
            height=52,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[10, 10],
            cursor_color=COLORS['DARK_BLUE']
        )
        qty_layout.add_widget(self.qty_input)
        layout.add_widget(qty_layout)

        self.info_label = Label(
            text='',
            size_hint_y=0.12,
            font_size='15sp',
            halign='left',
            color=COLORS['MEDIUM_GREY']
        )
        self.info_label.bind(size=self.info_label.setter('text_size'))
        layout.add_widget(self.info_label)

        delivery_layout = BoxLayout(size_hint_y=0.1)
        self.delivery_btn = Button(
            text='Доставка: ВКЛ',
            background_color=COLORS['DARK_BLUE'],
            color=(1, 1, 1, 1),
            font_size='17sp',
            size_hint_y=None,
            height=52
        )
        self.delivery_btn.bind(on_press=self.toggle_delivery)
        delivery_layout.add_widget(self.delivery_btn)
        layout.add_widget(delivery_layout)

        items_layout = BoxLayout(orientation='vertical', size_hint_y=0.25)
        items_layout.add_widget(Label(
            text='Позиции заказа:',
            color=COLORS['DARK_TEXT'],
            font_size='17sp',
            size_hint_y=None,
            height=32
        ))
        
        self.items_scroll = ScrollView(size_hint_y=0.8)
        self.items_list = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.items_list.bind(minimum_height=self.items_list.setter('height'))
        self.items_scroll.add_widget(self.items_list)
        items_layout.add_widget(self.items_scroll)
        layout.add_widget(items_layout)

        total_layout = BoxLayout(orientation='vertical', size_hint_y=0.2)
        self.total_label = Label(
            text='Итого: 0.00 ₽',
            font_size='21sp',
            bold=True,
            color=COLORS['DARK_TEXT'],
            size_hint_y=0.4
        )
        total_layout.add_widget(self.total_label)

        buttons_layout = BoxLayout(spacing=11, size_hint_y=0.6)
        
        add_btn = Button(
            text='Добавить',
            background_color=COLORS['DARK_BLUE'],
            color=(1, 1, 1, 1),
            font_size='16sp',
            size_hint_y=None,
            height=52
        )
        
        save_btn = Button(
            text='Сохранить',
            background_color=COLORS['GREEN'],
            color=(1, 1, 1, 1),
            font_size='16sp',
            size_hint_y=None,
            height=52
        )
        
        add_btn.bind(on_press=self.add_item)
        save_btn.bind(on_press=self.save_order)
        
        buttons_layout.add_widget(add_btn)
        buttons_layout.add_widget(save_btn)
        total_layout.add_widget(buttons_layout)
        layout.add_widget(total_layout)
        
        self.add_widget(layout)

    def on_enter(self):
        profile_data = self.get_profile_data()
        self.current_order_number = profile_data.get("next_order_number", 1)
        self.title_label.text = f'Заказ №{self.current_order_number}'
        self.order_items = []
        self.items_list.clear_widgets()

    def show_product_dropdown(self, instance):
        profile_data = self.get_profile_data()
        products = [
            p["name"] for p in profile_data.get("products", [])
            if profile_data["stock"].get(p["name"], {"current_quantity": 0})["current_quantity"] > 0
        ]
        
        if not products:
            self.show_popup('Ошибка', 'Нет товаров с остатком на складе')
            return
        
        dropdown = DropDown()
        for product in products:
            btn = Button(
                text=product,
                size_hint_y=None,
                height=42,
                background_color=COLORS['WHITE'],
                color=COLORS['DARK_TEXT'],
                font_size='17sp'
            )
            btn.bind(on_release=lambda btn, p=product: self.select_product(p, dropdown))
            dropdown.add_widget(btn)
        
        dropdown.open(self.product_btn)

    def select_product(self, product_name, dropdown):
        self.product_btn.text = product_name
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
                f"Стоимость: {product['cost_price']:.2f} ₽/кг | "
                f"Прибыль: {product['profit']:.2f} ₽ ({percent_profit:.1f}%) | "
                f"Остаток: {stock_data['current_quantity']:.2f} кг"
            )
            self.info_label.text = info_text

    def toggle_delivery(self, instance):
        self.delivery_enabled = not self.delivery_enabled
        self.delivery_btn.text = 'Доставка: ВКЛ' if self.delivery_enabled else 'Доставка: ВЫКЛ'
        self.delivery_btn.background_color = COLORS['DARK_BLUE'] if self.delivery_enabled else COLORS['RED']
        self.update_total()

    def add_item(self, instance):
        product_name = self.product_btn.text
        if product_name == 'Выберите товар':
            self.show_popup('Ошибка', 'Выберите товар')
            return
        
        qty, error = Validators.validate_positive_float(self.qty_input.text, "Количество")
        if error:
            self.show_popup('Ошибка', error)
            return
        
        profile_data = self.get_profile_data()
        stock_data = profile_data["stock"].get(product_name, {"current_quantity": 0.0})
        
        if qty > stock_data["current_quantity"]:
            self.show_popup(
                'Ошибка',
                f'Недостаточно товара. Доступно: {stock_data["current_quantity"]:.2f} кг'
            )
            return
        
        product = next((p for p in profile_data["products"] if p["name"] == product_name), None)
        if not product:
            self.show_popup('Ошибка', 'Товар не найден')
            return
        
        item = {
            "product": product_name,
            "quantity": qty,
            "cost_price": product["cost_price"],
            "total": qty * product["cost_price"]
        }
        
        self.order_items.append(item)
        
        item_label = Label(
            text=f'{product_name} × {qty:.1f} кг = {item["total"]:.2f} ₽',
            size_hint_y=None,
            height=42,
            color=COLORS['DARK_TEXT'],
            font_size='16sp'
        )
        self.items_list.add_widget(item_label)
        self.update_total()

    def update_total(self):
        subtotal = sum(item["total"] for item in self.order_items)
        total_weight = sum(item["quantity"] for item in self.order_items)
        delivery = self.business_logic.calculate_delivery_cost(total_weight) if self.delivery_enabled and total_weight > 0 else 0
        total = subtotal + delivery
        self.total_label.text = f'Итого: {total:.2f} ₽'

    def save_order(self, instance):
        if not self.order_items:
            self.show_popup('Ошибка', 'Добавьте товары в заказ')
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
                    'Ошибка',
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
        self.product_btn.text = 'Выберите товар'
        self.qty_input.text = '1.0'
        self.total_label.text = 'Итого: 0.00 ₽'
        
        self.show_popup(
            'Успех',
            f'Заказ №{order_number} сохранен!\nИтого: {total:.2f} ₽',
            callback=lambda: setattr(self.manager, 'current', 'profile')
        )

# ============================================================================
# ЭКРАН: АНАЛИЗ ПРОДАЖ
# ============================================================================
class SalesAnalysisScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._table_w = get_table_width()
        self.build_ui()

    def build_ui(self):
        self._table_w = get_table_width()
        layout = BoxLayout(orientation='vertical', padding=[12, 12, 12, 16], spacing=8)
        layout.add_widget(UIComponents.create_back_button('profile'))
        
        title = Label(
            text='Анализ продаж',
            size_hint_y=0.08,
            font_size='26sp',
            bold=True,
            color=COLORS['DARK_BLUE'],
            halign='center'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)

        hint_label = Label(
            text='Выберите период и товар для анализа',
            size_hint_y=0.05,
            font_size='17sp',
            color=COLORS['MEDIUM_GREY'],
            italic=True,
            halign='center'
        )
        hint_label.bind(size=hint_label.setter('text_size'))
        layout.add_widget(hint_label)

        filters_layout = BoxLayout(orientation='vertical', size_hint_y=0.24, spacing=12)
        
        # Дата от
        date_from_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=70)
        date_from_layout.add_widget(Label(
            text='Начало периода:',
            color=COLORS['DARK_BLUE'],
            font_size='17sp',
            bold=True,
            size_hint_y=None,
            height=32
        ))
        
        self.date_from_input = TextInput(
            text=(date.today() - timedelta(days=30)).isoformat(),
            multiline=False,
            font_size='13sp',
            height=36,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[15, 11],
            hint_text='ГГГГ-ММ-ДД',
            cursor_color=COLORS['DARK_BLUE']
        )
        date_from_layout.add_widget(self.date_from_input)
        filters_layout.add_widget(date_from_layout)
        
        # Дата до
        date_to_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=70)
        date_to_layout.add_widget(Label(
            text='Конец периода:',
            color=COLORS['DARK_BLUE'],
            font_size='17sp',
            bold=True,
            size_hint_y=None,
            height=32
        ))
        
        self.date_to_input = TextInput(
            text=date.today().isoformat(),
            multiline=False,
            font_size='13sp',
            height=36,
            size_hint_y=None,
            background_color=COLORS['WHITE'],
            foreground_color=COLORS['DARK_TEXT'],
            padding=[15, 11],
            hint_text='ГГГГ-ММ-ДД',
            cursor_color=COLORS['DARK_BLUE']
        )
        date_to_layout.add_widget(self.date_to_input)
        filters_layout.add_widget(date_to_layout)
        
        # Выбор товара
        product_filter_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=70)
        product_filter_layout.add_widget(Label(
            text='Фильтр по товару:',
            color=COLORS['DARK_BLUE'],
            font_size='17sp',
            bold=True,
            size_hint_y=None,
            height=32
        ))
        
        self.product_dropdown_btn = Button(
            text='Все товары',
            size_hint_y=None,
            height=36,
            background_color=COLORS['LIGHT_BG'],
            color=COLORS['DARK_TEXT'],
            font_size='17sp',
            bold=True
        )
        self.product_dropdown_btn.bind(on_press=self.show_product_dropdown)
        product_filter_layout.add_widget(self.product_dropdown_btn)
        filters_layout.add_widget(product_filter_layout)
        
        layout.add_widget(filters_layout)

        # Кнопки фильтрации — единый размер
        btn_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=BTN_ACTION_H + 8, spacing=12)
        apply_btn = UIComponents.create_primary_button('Применить')
        apply_btn.background_color = COLORS['GREEN']
        clear_btn = UIComponents.create_secondary_button('Сбросить')
        clear_btn.background_color = COLORS['AMBER']
        clear_btn.color = (1, 1, 1, 1)
        apply_btn.bind(on_press=self.load_analysis)
        clear_btn.bind(on_press=self.clear_filters)
        btn_layout.add_widget(apply_btn)
        btn_layout.add_widget(clear_btn)
        layout.add_widget(btn_layout)

        # Результаты анализа (таблица приподнята, горизонтальный скролл)
        results_title = Label(
            text='Результаты анализа (свайп влево/вправо — все столбцы)',
            size_hint_y=0.055,
            font_size='18sp',
            bold=True,
            color=COLORS['DARK_BLUE'],
            halign='center'
        )
        results_title.bind(size=results_title.setter('text_size'))
        layout.add_widget(results_title)

        scroll = ScrollView(
            size_hint_y=0.54,
            do_scroll_x=True,
            do_scroll_y=True,
            bar_width=10,
            scroll_type=['bars', 'content'],
            bar_color=COLORS['DARK_BLUE'][:3] + (0.85,),
            bar_inactive_color=COLORS['LIGHT_GREY'][:3] + (0.65,),
        )
        self.analysis_scroll = scroll
        w = self._table_w
        self.analysis_container = BoxLayout(orientation='vertical', size_hint_x=None, width=w)
        self.analysis_list = GridLayout(cols=1, spacing=10, size_hint_y=None, size_hint_x=None, width=w)
        self.analysis_list.bind(minimum_height=self.analysis_list.setter('height'))
        self.analysis_container.add_widget(self.analysis_list)
        scroll.add_widget(self.analysis_container)
        layout.add_widget(scroll)
        
        self.add_widget(layout)

    def on_enter(self):
        self.load_products_for_dropdown()
        self.load_analysis(None)

    def load_products_for_dropdown(self):
        profile_data = self.get_profile_data()
        products = [p["name"] for p in profile_data.get("products", [])]
        self.product_list = ["Все товары"] + sorted(products)

    def show_product_dropdown(self, instance):
        dropdown = DropDown()
        for product_name in self.product_list:
            btn = Button(
                text=product_name,
                size_hint_y=None,
                height=50,
                background_color=COLORS['WHITE'],
                color=COLORS['DARK_TEXT'],
                font_size='17sp'
            )
            btn.bind(on_release=lambda btn, p=product_name: self.select_product(p, dropdown))
            dropdown.add_widget(btn)
        
        dropdown.open(self.product_dropdown_btn)

    def select_product(self, product_name, dropdown):
        self.product_dropdown_btn.text = product_name
        dropdown.dismiss()

    def clear_filters(self, instance):
        self.date_from_input.text = (date.today() - timedelta(days=30)).isoformat()
        self.date_to_input.text = date.today().isoformat()
        self.product_dropdown_btn.text = 'Все товары'
        self.load_analysis(None)

    def load_analysis(self, instance):
        self.analysis_list.clear_widgets()
        self._table_w = get_table_width()
        self.analysis_container.width = self._table_w
        
        date_from, error = Validators.validate_date(self.date_from_input.text)
        if error:
            self.show_popup('Ошибка', f'Неверный формат даты "от": {error}')
            return
        
        date_to, error = Validators.validate_date(self.date_to_input.text)
        if error:
            self.show_popup('Ошибка', f'Неверный формат даты "до": {error}')
            return
        
        if date_from > date_to:
            self.show_popup('Ошибка', 'Дата "от" не может быть больше даты "до"')
            return
        
        selected_product = self.product_dropdown_btn.text
        filter_by_product = selected_product != "Все товары"
        
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
            except Exception as e:
                print(f"[!] Ошибка обработки заказа: {e}")
                continue
        
        # Заголовок таблицы
        header_labels = [
            ("Дата", 0.14),
            ("Товар", 0.24),
            ("Количество", 0.14),
            ("Сумма в день", 0.16),
            ("Выручка", 0.16),
            ("Затраты", 0.16)
        ]
        
        header_card = UIComponents.create_table_header(header_labels, width=self._table_w)
        self.analysis_list.add_widget(header_card)
        
        # Проверка на отсутствие данных
        if not sales_data:
            empty_label = Label(
                text='Нет данных для выбранного периода',
                size_hint_y=None,
                height=72,
                color=COLORS['MEDIUM_GREY'],
                font_size='21sp',
                bold=True,
                halign='center'
            )
            empty_label.bind(size=empty_label.setter('text_size'))
            self.analysis_list.add_widget(empty_label)
            
            hint_label = Label(
                text='Измените период или добавьте заказы',
                size_hint_y=None,
                height=48,
                color=COLORS['LIGHT_GREY'],
                font_size='16sp',
                halign='center',
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
                
                bg_color = COLORS['WHITE'] if row_index % 2 == 0 else (0.97, 0.985, 1.0, 1)
                
                card = BoxLayout(
                    orientation='horizontal',
                    size_hint_y=None,
                    height=66,
                    padding=[13, 10],
                    spacing=8,
                    size_hint_x=None,
                    width=self._table_w
                )
                
                with card.canvas.before:
                    Color(*bg_color)
                    card.rect = Rectangle(pos=card.pos, size=card.size)
                    Color(0.90, 0.90, 0.90, 1)
                    card.line = Line(points=[card.x, card.y, card.right, card.y], width=1)
                
                def update_line(instance, value):
                    instance.rect.pos = instance.pos
                    instance.rect.size = instance.size
                    instance.line.points = [instance.x, instance.y, instance.right, instance.y]
                
                card.bind(pos=update_line, size=update_line)
                
                for text, width_ratio, color in [
                    (day_date_str, 0.14, COLORS['DARK_TEXT']),
                    (product_name, 0.24, COLORS['DARK_BLUE']),
                    (f"{qty:.1f} кг", 0.14, COLORS['AMBER']),
                    (f"{daily_sum:,.0f} ₽".replace(",", " "), 0.16, COLORS['GREEN']),
                    (f"{profit_calc:,.0f} ₽".replace(",", " "), 0.16, COLORS['PURPLE']),
                    (f"{expense_calc:,.0f} ₽".replace(",", " "), 0.16, COLORS['ORANGE'])
                ]:
                    label = Label(
                        text=text,
                        font_size='17sp',
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
            height=70,
            padding=[13, 10],
            spacing=8,
            size_hint_x=None,
            width=self._table_w
        )
        
        with total_card.canvas.before:
            Color(0.94, 1.0, 0.94, 1)
            total_card.rect = Rectangle(pos=total_card.pos, size=total_card.size)
            Color(0.15, 0.60, 0.20, 1)
            total_card.border = Line(rectangle=(total_card.x, total_card.y, total_card.width, total_card.height), width=2.5)
        
        def update_total_rect(instance, value):
            instance.rect.pos = instance.pos
            instance.rect.size = instance.size
        
        total_card.bind(pos=update_total_rect, size=update_total_rect)
        
        total_items = [
            ("ИТОГО", 0.14, COLORS['DARK_BLUE']),
            ("", 0.24, COLORS['DARK_TEXT']),
            (f"{total_qty:.1f} кг", 0.14, COLORS['AMBER']),
            (f"{total_sum:,.0f} ₽".replace(",", " "), 0.16, COLORS['GREEN']),
            (f"{total_profit:,.0f} ₽".replace(",", " "), 0.16, COLORS['PURPLE']),
            (f"{total_expense:,.0f} ₽".replace(",", " "), 0.16, COLORS['ORANGE'])
        ]
        
        for text, width_ratio, color in total_items:
            label = Label(
                text=text,
                font_size='18sp',
                bold=True,
                color=color,
                size_hint_x=width_ratio,
                halign='center',
                valign='middle'
            )
            label.bind(size=label.setter('text_size'))
            total_card.add_widget(label)
        
        self.analysis_list.add_widget(total_card)

# ============================================================================
# ЭКРАН: ИСТОРИЯ ЗАКАЗОВ
# ============================================================================
class OrderHistoryScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._table_w = get_table_width()
        self.build_ui()

    def build_ui(self):
        self._table_w = get_table_width()
        layout = BoxLayout(orientation='vertical', padding=[12, 12, 12, 16], spacing=8)
        layout.add_widget(UIComponents.create_back_button('profile'))
        
        title = Label(
            text='История заказов',
            size_hint_y=0.07,
            font_size='25sp',
            bold=True,
            color=COLORS['PINK'],
            halign='center'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)

        scroll = ScrollView(size_hint_y=0.22)
        self.history_list = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.history_list.bind(minimum_height=self.history_list.setter('height'))
        scroll.add_widget(self.history_list)
        layout.add_widget(scroll)

        stats_title = Label(
            text='Дневная статистика (свайп влево/вправо — все столбцы)',
            size_hint_y=0.05,
            font_size='18sp',
            bold=True,
            color=COLORS['DARK_BLUE'],
            halign='center'
        )
        stats_title.bind(size=stats_title.setter('text_size'))
        layout.add_widget(stats_title)

        stats_scroll = ScrollView(
            size_hint_y=0.58,
            do_scroll_x=True,
            do_scroll_y=True,
            bar_width=10,
            scroll_type=['bars', 'content'],
            bar_color=COLORS['DARK_BLUE'][:3] + (0.85,),
            bar_inactive_color=COLORS['LIGHT_GREY'][:3] + (0.65,),
        )
        self.stats_scroll = stats_scroll
        w = self._table_w
        self.stats_container = BoxLayout(orientation='vertical', size_hint_x=None, width=w)
        self.stats_list = GridLayout(cols=1, spacing=7, size_hint_y=None, size_hint_x=None, width=w)
        self.stats_list.bind(minimum_height=self.stats_list.setter('height'))
        self.stats_container.add_widget(self.stats_list)
        stats_scroll.add_widget(self.stats_container)
        layout.add_widget(stats_scroll)
        
        self.add_widget(layout)

    def on_enter(self):
        self.load_history()
        self.load_daily_stats()

    def load_history(self):
        self.history_list.clear_widgets()
        profile_data = self.get_profile_data()
        orders = profile_data.get("orders", [])
        
        if not orders:
            empty_label = Label(
                text='Нет завершенных заказов',
                size_hint_y=None,
                height=60,
                color=COLORS['MEDIUM_GREY'],
                font_size='21sp',
                bold=True,
                halign='center'
            )
            empty_label.bind(size=empty_label.setter('text_size'))
            self.history_list.add_widget(empty_label)
            return
        
        for order in sorted(orders, key=lambda x: x["number"], reverse=True)[:15]:
            card = BoxLayout(
                orientation='vertical',
                size_hint_y=None,
                height=108,
                padding=[12, 6],
                spacing=3
            )
            
            num_label = Label(
                text=f"Заказ №{order['number']} от {order['date']}",
                font_size='17sp',
                bold=True,
                color=COLORS['DARK_TEXT'],
                size_hint_y=None,
                height=30
            )
            
            items_label = Label(
                text=f"Товаров: {len(order['items'])} | Вес: {sum(i['quantity'] for i in order['items']):.1f} кг",
                font_size='15sp',
                color=COLORS['DARK_TEXT'],
                size_hint_y=None,
                height=26
            )
            
            total_label = Label(
                text=f"Итого: {order['total']:.2f} ₽ (доставка: {order['delivery_cost']} ₽)",
                font_size='16sp',
                color=COLORS['GREEN'],
                size_hint_y=None,
                height=28
            )
            
            card.add_widget(num_label)
            card.add_widget(items_label)
            card.add_widget(total_label)
            self.history_list.add_widget(card)

    def load_daily_stats(self):
        """Загружает дневную статистику из профиля с КОРРЕКТНЫМ расчётом суммы доставки"""
        self.stats_list.clear_widgets()
        self._table_w = get_table_width()
        self.stats_container.width = self._table_w
        
        profile_data = self.get_profile_data()
        daily_stats = profile_data.get("daily_stats", {})
        
        header_labels = [
            ("Дата", 0.18),
            ("Кол-во заказов", 0.18),
            ("С доставкой", 0.18),
            ("Сумма за день", 0.18),
            ("Сумма доставки", 0.18),
            ("Общая выручка", 0.18)
        ]
        
        header_card = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=50,
            padding=[9, 0],
            spacing=6,
            size_hint_x=None,
            width=self._table_w
        )
        
        with header_card.canvas.before:
            Color(0.10, 0.40, 0.80, 1)
            header_card.rect = Rectangle(pos=header_card.pos, size=header_card.size)
        
        def update_header_rect(instance, value):
            instance.rect.pos = instance.pos
            instance.rect.size = instance.size
        
        header_card.bind(pos=update_header_rect, size=update_header_rect)
        
        for text, width_ratio in header_labels:
            lbl = Label(
                text=text,
                font_size='16sp',
                bold=True,
                color=(1, 1, 1, 1),
                size_hint_x=width_ratio,
                halign='center',
                valign='middle'
            )
            lbl.bind(size=lbl.setter('text_size'))
            header_card.add_widget(lbl)
        
        self.stats_list.add_widget(header_card)
        
        for date_key, data in sorted(daily_stats.items(), reverse=True):
            card = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=60,
                padding=[9, 0],
                spacing=6,
                size_hint_x=None,
                width=self._table_w
            )
            
            with card.canvas.before:
                Color(1, 1, 1, 1)
                card.rect = Rectangle(pos=card.pos, size=card.size)
                Color(0.92, 0.92, 0.92, 1)
                card.line = Line(points=[card.x, card.y, card.right, card.y], width=0.6)
            
            def update_line(instance, value):
                instance.rect.pos = instance.pos
                instance.rect.size = instance.size
                instance.line.points = [instance.x, instance.y, instance.right, instance.y]
            
            card.bind(pos=update_line, size=update_line)
            
            date_label = Label(
                text=date_key,
                font_size='16sp',
                bold=True,
                color=COLORS['DARK_TEXT'],
                size_hint_x=0.18,
                halign='center',
                valign='middle'
            )
            date_label.bind(size=date_label.setter('text_size'))
            
            orders_label = Label(
                text=str(data["orders_count"]),
                font_size='17sp',
                bold=True,
                color=COLORS['DARK_BLUE'],
                size_hint_x=0.18,
                halign='center',
                valign='middle'
            )
            orders_label.bind(size=orders_label.setter('text_size'))
            
            delivery_label = Label(
                text=str(data["delivery_count"]),
                font_size='17sp',
                bold=True,
                color=COLORS['AMBER'],
                size_hint_x=0.18,
                halign='center',
                valign='middle'
            )
            delivery_label.bind(size=delivery_label.setter('text_size'))
            
            sum_day_label = Label(
                text=f"{int(data['total_revenue']):,}".replace(",", " "),
                font_size='17sp',
                bold=True,
                color=COLORS['GREEN'],
                size_hint_x=0.18,
                halign='center',
                valign='middle'
            )
            sum_day_label.bind(size=sum_day_label.setter('text_size'))
            
            # ИСПРАВЛЕНО: Сумма доставки = ТОЛЬКО сумма стоимостей доставки
            delivery_sum_label = Label(
                text=f"{int(data['delivery_sum']):,}".replace(",", " "),
                font_size='17sp',
                bold=True,
                color=COLORS['ORANGE'],
                size_hint_x=0.18,
                halign='center',
                valign='middle'
            )
            delivery_sum_label.bind(size=delivery_sum_label.setter('text_size'))
            
            revenue_label = Label(
                text=f"{int(data['total_revenue'] - data['delivery_sum']):,}".replace(",", " "),
                font_size='17sp',
                bold=True,
                color=COLORS['PURPLE'],
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

# ============================================================================
# ЭКРАН: ИСТОРИЯ ОПЕРАЦИЙ СО СКЛАДОМ
# ============================================================================
class StockHistoryScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=12, spacing=12)
        layout.add_widget(UIComponents.create_back_button('warehouse', 'Назад'))
        
        title = Label(
            text='История операций со складом',
            size_hint_y=0.08,
            font_size='23sp',
            bold=True,
            color=COLORS['TEAL'],
            halign='center'
        )
        title.bind(size=title.setter('text_size'))
        layout.add_widget(title)

        scroll = ScrollView(
            size_hint_y=0.85,
            do_scroll_x=True,
            bar_width=13,
            scroll_type=['bars', 'content'],
            bar_color=COLORS['DARK_BLUE'][:3] + (0.85,),
            bar_inactive_color=COLORS['LIGHT_GREY'][:3] + (0.65,)
        )
        
        self.history_container = BoxLayout(orientation='vertical', size_hint_x=None, width=1100)
        self.history_list = GridLayout(cols=1, spacing=9, size_hint_y=None, size_hint_x=None, width=1100)
        self.history_list.bind(minimum_height=self.history_list.setter('height'))
        self.history_container.add_widget(self.history_list)
        scroll.add_widget(self.history_container)
        layout.add_widget(scroll)
        
        self.add_widget(layout)

    def on_enter(self):
        self.load_history()

    def load_history(self):
        self.history_list.clear_widgets()
        self.history_container.width = 1100
        
        profile_data = self.get_profile_data()
        stock_data = profile_data.get("stock", {})
        
        if not stock_data:
            empty_label = Label(
                text='Нет истории операций со складом.',
                size_hint_y=None,
                height=60,
                color=COLORS['MEDIUM_GREY'],
                font_size='21sp',
                bold=True,
                halign='center'
            )
            empty_label.bind(size=empty_label.setter('text_size'))
            self.history_list.add_widget(empty_label)
            return
        
        all_operations = []
        for product_name, data in stock_data.items():
            history = data.get("history", [])
            for op in history:
                op_dict = {
                    "date": op.get("date", ""),
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
            ("Дата", 0.17),
            ("Товар", 0.25),
            ("Операция", 0.17),
            ("Количество", 0.12),
            ("Цена закупки", 0.12),
            ("Сумма", 0.12),
            ("Остаток после", 0.12)
        ]
        
        header_card = UIComponents.create_table_header(header_labels, width=1100)
        self.history_list.add_widget(header_card)
        
        for op in all_operations[:50]:
            card = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=57,
                padding=[9, 6],
                spacing=6,
                size_hint_x=None,
                width=1100
            )
            
            for text, width_ratio in [
                (op["date"], 0.17),
                (op["product"], 0.25),
                (op["operation"].capitalize(), 0.17),
                (f"{op['quantity']:.2f}", 0.12),
                (f"{op['price_per_kg']:.2f}", 0.12),
                (f"{op['total_amount']:.2f}", 0.12),
                (f"{op['balance_after']:.2f}", 0.12)
            ]:
                label = Label(
                    text=text,
                    font_size='15sp',
                    color=COLORS['DARK_TEXT'],
                    size_hint_x=width_ratio,
                    halign='center'
                )
                label.bind(size=label.setter('text_size'))
                card.add_widget(label)
            
            self.history_list.add_widget(card)

# ============================================================================
# ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ============================================================================
class OrderApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_profile: Optional[str] = None
        self.profile_data: Dict = {}
        self.product_to_edit: Optional[Dict] = None
        
        # Инициализация модулей
        self.data_manager = DataManager()
        self.business_logic = BusinessLogic()

    def build(self):
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
        Window.clearcolor = COLORS['LIGHT_BG']
        return sm

    try:
        from kivy.app import App
        app = App.get_running_app()
        if hasattr(app, 'data_manager') and app.data_manager.profiles_file:
            profiles_file = app.data_manager.profiles_file
            if os.path.exists(profiles_file) and os.path.getsize(profiles_file) == 0:
                os.remove(profiles_file)
    except Exception as e:
        print(f"⚠ Ошибка очистки файлов: {e}")
        
    def request_android_permissions(self):
        try:
            import importlib
            if importlib.util.find_spec("android") is not None:
                android_module = __import__('android.permissions',
                                           fromlist=['request_permissions', 'Permission'])
                request_permissions = android_module.request_permissions
                Permission = android_module.Permission
                request_permissions([
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE
                ])
                print("[OK] Запрошены разрешения для Android")
        except Exception as e:
            print(f"[!] Android permissions error: {e}")

# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================
if __name__ == '__main__':
    OrderApp().run()