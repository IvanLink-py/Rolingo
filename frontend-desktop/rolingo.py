import sys
import httpx
from datetime import datetime
from PySide6.QtCore import Qt, QThread, Signal, QSettings, QSize
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QScrollArea, QFrame, QTextEdit, QMessageBox,
    QSizePolicy, QSpacerItem, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QGroupBox
)
from PySide6.QtGui import QFont, QColor, QPalette

BASE_URL = "http://localhost:9050/api/v1"


# ── API CLIENT ────────────────────────────────────────────────────────────────

class ApiError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


class ApiClient:
    def __init__(self):
        self._access_token = None
        self._refresh_token = None

    def set_tokens(self, access, refresh):
        self._access_token = access
        self._refresh_token = refresh

    def clear_tokens(self):
        self._access_token = None
        self._refresh_token = None

    @property
    def refresh_token(self):
        return self._refresh_token

    def _headers(self):
        return {"Authorization": f"Bearer {self._access_token}"} if self._access_token else {}

    def _raise(self, r):
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise ApiError(str(detail))

    def _try_refresh(self):
        if not self._refresh_token:
            raise ApiError("Session expired")
        r = httpx.post(f"{BASE_URL}/auth/refresh", json={"refresh_token": self._refresh_token}, timeout=10)
        if r.status_code != 200:
            self.clear_tokens()
            raise ApiError("Session expired, please log in again")
        data = r.json()
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]

    def _get(self, path, **kwargs):
        r = httpx.get(f"{BASE_URL}{path}", headers=self._headers(), timeout=30, **kwargs)
        if r.status_code == 401:
            self._try_refresh()
            r = httpx.get(f"{BASE_URL}{path}", headers=self._headers(), timeout=30, **kwargs)
        if not r.is_success:
            self._raise(r)
        return r.json()

    def _post(self, path, json=None, auth=True):
        h = self._headers() if auth else {}
        r = httpx.post(f"{BASE_URL}{path}", json=json, headers=h, timeout=60)
        if r.status_code == 401 and auth:
            self._try_refresh()
            r = httpx.post(f"{BASE_URL}{path}", json=json, headers=self._headers(), timeout=60)
        if not r.is_success:
            self._raise(r)
        return r.json() if r.content else {}

    def _patch(self, path, json=None):
        r = httpx.patch(f"{BASE_URL}{path}", json=json, headers=self._headers(), timeout=60)
        if r.status_code == 401:
            self._try_refresh()
            r = httpx.patch(f"{BASE_URL}{path}", json=json, headers=self._headers(), timeout=60)
        if not r.is_success:
            self._raise(r)
        return r.json() if r.content else {}

    # Auth
    def register(self, username, email, password):
        return self._post("/auth/register", {"username": username, "email": email, "password": password}, auth=False)

    def login(self, email, password):
        return self._post("/auth/login", {"email": email, "password": password}, auth=False)

    def logout(self):
        try:
            self._post("/auth/logout", {"refresh_token": self._refresh_token})
        except Exception:
            pass
        self.clear_tokens()

    # Users
    def me(self):
        return self._get("/users/me")

    def update_me(self, **kwargs):
        return self._patch("/users/me", {k: v for k, v in kwargs.items() if v is not None})

    def complete_onboarding(self):
        return self._post("/users/me/complete-onboarding")

    # Scenarios
    def scenarios(self, language=None, dialog_type=None, page=1, limit=20):
        params = {"page": page, "limit": limit}
        if language:
            params["language"] = language
        if dialog_type:
            params["dialog_type"] = dialog_type
        return self._get("/scenarios", params=params)

    # Sessions
    def create_session(self, scenario_id, dialog_type, difficulty):
        return self._post("/sessions", {"scenario_id": scenario_id, "dialog_type": dialog_type, "difficulty": difficulty})

    def sessions(self, page=1, limit=20):
        return self._get("/sessions", params={"page": page, "limit": limit})

    def finish_session(self, session_id):
        return self._patch(f"/sessions/{session_id}/finish")

    # Messages
    def send_message(self, session_id, content):
        return self._post(f"/sessions/{session_id}/messages", {"content": content})

    def get_messages(self, session_id):
        return self._get(f"/sessions/{session_id}/messages")


api = ApiClient()


# ── WORKER THREAD ─────────────────────────────────────────────────────────────

class Worker(QThread):
    result = Signal(object)
    error = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.result.emit(self._fn())
        except ApiError as e:
            self.error.emit(e.message)
        except Exception as e:
            self.error.emit(str(e))


# ── HELPERS ───────────────────────────────────────────────────────────────────

def make_button(text, primary=True, small=False):
    btn = QPushButton(text)
    h = 32 if small else 38
    btn.setFixedHeight(h)
    if primary:
        btn.setStyleSheet(
            "QPushButton { background: #0078d4; color: white; border: none; border-radius: 4px; padding: 0 16px; font-size: 13px; }"
            "QPushButton:hover { background: #106ebe; }"
            "QPushButton:disabled { background: #ccc; }"
        )
    else:
        btn.setStyleSheet(
            "QPushButton { background: transparent; color: #0078d4; border: 1px solid #0078d4; border-radius: 4px; padding: 0 16px; font-size: 13px; }"
            "QPushButton:hover { background: #e8f0fe; }"
        )
    return btn


def make_input(placeholder="", password=False):
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    w.setFixedHeight(36)
    w.setStyleSheet("QLineEdit { border: 1px solid #ccc; border-radius: 4px; padding: 0 8px; font-size: 13px; }"
                    "QLineEdit:focus { border-color: #0078d4; }")
    if password:
        w.setEchoMode(QLineEdit.Password)
    return w


def make_combo(items):
    c = QComboBox()
    c.addItems(items)
    c.setFixedHeight(36)
    c.setStyleSheet("QComboBox { border: 1px solid #ccc; border-radius: 4px; padding: 0 8px; font-size: 13px; }"
                    "QComboBox:focus { border-color: #0078d4; }"
                    "QComboBox::drop-down { border: none; }")
    return c


def make_label(text, bold=False, color=None, size=13):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"font-size: {size}px; {'font-weight: bold;' if bold else ''} {'color: ' + color + ';' if color else ''}")
    return lbl


def separator():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: #e0e0e0;")
    return line


def run_worker(parent, fn, on_result, on_error=None, btn=None):
    if btn:
        btn.setEnabled(False)
    w = Worker(fn)

    def _done(r):
        if btn:
            btn.setEnabled(True)
        on_result(r)

    def _err(e):
        if btn:
            btn.setEnabled(True)
        if on_error:
            on_error(e)
        else:
            QMessageBox.warning(parent, "Ошибка", e)

    w.result.connect(_done)
    w.error.connect(_err)
    parent._workers = getattr(parent, "_workers", [])
    parent._workers.append(w)
    w.start()


# ── SCREENS ───────────────────────────────────────────────────────────────────

class AuthScreen(QWidget):
    """Login / Register"""
    logged_in = Signal()

    def __init__(self):
        super().__init__()
        self._mode = "login"
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        box = QWidget()
        box.setFixedWidth(360)
        lay = QVBoxLayout(box)
        lay.setSpacing(10)

        self._title = make_label("Rolingo", bold=True, size=24)
        self._title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._title)
        lay.addWidget(make_label("Учи язык в ролевых диалогах", color="#666", size=13))
        lay.addSpacing(16)

        self._name_input = make_input("Имя пользователя")
        self._name_input.hide()
        lay.addWidget(self._name_input)

        self._email = make_input("Email")
        self._pass = make_input("Пароль", password=True)
        lay.addWidget(self._email)
        lay.addWidget(self._pass)

        self._btn = make_button("Войти")
        self._btn.clicked.connect(self._submit)
        self._pass.returnPressed.connect(self._submit)
        lay.addWidget(self._btn)

        self._switch = QPushButton("Нет аккаунта? Зарегистрироваться")
        self._switch.setFlat(True)
        self._switch.setStyleSheet("color: #0078d4; font-size: 12px; border: none;")
        self._switch.clicked.connect(self._toggle)
        lay.addWidget(self._switch, alignment=Qt.AlignCenter)

        root.addWidget(box, alignment=Qt.AlignCenter)

    def _toggle(self):
        self._mode = "register" if self._mode == "login" else "login"
        if self._mode == "register":
            self._name_input.show()
            self._btn.setText("Зарегистрироваться")
            self._switch.setText("Уже есть аккаунт? Войти")
        else:
            self._name_input.hide()
            self._btn.setText("Войти")
            self._switch.setText("Нет аккаунта? Зарегистрироваться")

    def _submit(self):
        email = self._email.text().strip()
        password = self._pass.text()
        if self._mode == "login":
            fn = lambda: api.login(email, password)
        else:
            name = self._name_input.text().strip()
            fn = lambda: api.register(name, email, password)

        def done(data):
            api.set_tokens(data["access_token"], data["refresh_token"])
            settings = QSettings("Rolingo", "Desktop")
            settings.setValue("refresh_token", data["refresh_token"])
            self.logged_in.emit()

        run_worker(self, fn, done, btn=self._btn)


class OnboardingScreen(QWidget):
    done = Signal()

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        box = QWidget()
        box.setFixedWidth(380)
        lay = QVBoxLayout(box)
        lay.setSpacing(12)

        lay.addWidget(make_label("Настройка профиля", bold=True, size=18))
        lay.addWidget(make_label("Заполни один раз — сохранится везде", color="#666"))
        lay.addSpacing(8)

        lay.addWidget(make_label("Язык интерфейса"))
        self._iface = make_combo(["Русский (ru)", "English (en)"])
        lay.addWidget(self._iface)

        lay.addWidget(make_label("Изучаемый язык"))
        self._target = make_combo(["English (en)", "Русский (ru)"])
        lay.addWidget(self._target)

        lay.addWidget(make_label("Уровень владения"))
        self._level = make_combo(["A1", "A2", "B1", "B2", "C1", "C2"])
        lay.addWidget(self._level)

        lay.addWidget(make_label("Возрастная группа"))
        self._age = make_combo(["Взрослый (adult)", "Подросток (teen)"])
        lay.addWidget(self._age)

        lay.addSpacing(8)
        btn = make_button("Сохранить и начать")
        btn.clicked.connect(lambda: self._save(btn))
        lay.addWidget(btn)

        root.addWidget(box, alignment=Qt.AlignCenter)

    def _save(self, btn):
        iface = "ru" if self._iface.currentIndex() == 0 else "en"
        target = "en" if self._target.currentIndex() == 0 else "ru"
        level = self._level.currentText()
        age = "adult" if self._age.currentIndex() == 0 else "teen"

        def fn():
            api.update_me(interface_language=iface, target_language=target,
                          lang_level=level, age_group=age)
            api.complete_onboarding()

        run_worker(self, fn, lambda _: self.done.emit(), btn=btn)


class ScenarioCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, scenario):
        super().__init__()
        self._s = scenario
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "QFrame { border: 1px solid #e0e0e0; border-radius: 6px; background: white; }"
            "QFrame:hover { border-color: #0078d4; background: #f5f9ff; }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        top = QHBoxLayout()
        top.addWidget(make_label(scenario["title"], bold=True))
        badge_text = "Mission" if scenario["dialog_type"] == "mission" else "Hangout"
        badge = make_label(badge_text, color="#0078d4", size=11)
        top.addWidget(badge, alignment=Qt.AlignRight)
        lay.addLayout(top)

        lay.addWidget(make_label(scenario["description"], color="#555", size=12))

        meta = make_label(
            f"{scenario['character_name']} · {scenario['character_role']} · {scenario['min_level']}",
            color="#888", size=11
        )
        lay.addWidget(meta)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self._s)


class ScenariosScreen(QWidget):
    start_session = Signal(dict, str, str)  # scenario, dialog_type, difficulty

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        # Filters
        frow = QHBoxLayout()
        frow.addWidget(make_label("Язык:"))
        self._f_lang = make_combo(["Все", "en", "ru"])
        self._f_lang.setFixedWidth(80)
        frow.addWidget(self._f_lang)
        frow.addWidget(make_label("Тип:"))
        self._f_type = make_combo(["Все", "mission", "hangout"])
        self._f_type.setFixedWidth(100)
        frow.addWidget(self._f_type)
        frow.addStretch()
        load_btn = make_button("Обновить", primary=False, small=True)
        load_btn.clicked.connect(self.load)
        frow.addWidget(load_btn)
        root.addLayout(frow)
        root.addWidget(separator())

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._container = QWidget()
        self._lay = QVBoxLayout(self._container)
        self._lay.setSpacing(8)
        self._lay.addStretch()
        scroll.setWidget(self._container)
        root.addWidget(scroll)

        self._status = make_label("", color="#888", size=12)
        root.addWidget(self._status)

    def load(self):
        lang = self._f_lang.currentText()
        dtype = self._f_type.currentText()
        params = {}
        if lang != "Все":
            params["language"] = lang
        if dtype != "Все":
            params["dialog_type"] = dtype

        def fn():
            return api.scenarios(**params)

        run_worker(self, fn, self._render)

    def _render(self, data):
        # Clear
        while self._lay.count() > 1:
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        scenarios = data.get("scenarios", [])
        self._status.setText(f"Найдено: {data.get('total', 0)}")
        for s in scenarios:
            card = ScenarioCard(s)
            card.clicked.connect(self._pick)
            self._lay.insertWidget(self._lay.count() - 1, card)

    def _pick(self, scenario):
        dlg = StartDialog(scenario, self)
        if dlg.exec():
            self.start_session.emit(scenario, dlg.dialog_type(), dlg.difficulty())


class StartDialog(QDialog):
    def __init__(self, scenario, parent):
        super().__init__(parent)
        self.setWindowTitle("Начать сессию")
        self.setFixedWidth(320)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lay.addWidget(make_label(scenario["title"], bold=True, size=14))
        lay.addWidget(make_label(scenario["description"], color="#555", size=12))
        lay.addWidget(separator())

        lay.addWidget(make_label("Тип диалога"))
        self._type = make_combo(["mission", "hangout"])
        if scenario["dialog_type"]:
            idx = self._type.findText(scenario["dialog_type"])
            if idx >= 0:
                self._type.setCurrentIndex(idx)
        lay.addWidget(self._type)

        lay.addWidget(make_label("Сложность"))
        self._diff = make_combo(["relax", "challenge"])
        lay.addWidget(self._diff)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Начать")
        btns.button(QDialogButtonBox.Cancel).setText("Отмена")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def dialog_type(self):
        return self._type.currentText()

    def difficulty(self):
        return self._diff.currentText()


class SessionScreen(QWidget):
    finished = Signal(dict)
    back = Signal()

    def __init__(self):
        super().__init__()
        self._session_id = None
        self._difficulty = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        back_btn = make_button("← Назад", primary=False, small=True)
        back_btn.clicked.connect(self._confirm_back)
        hdr.addWidget(back_btn)
        self._hdr_label = make_label("", bold=True)
        hdr.addWidget(self._hdr_label, 1, Qt.AlignCenter)
        self._finish_btn = make_button("Завершить", small=True)
        self._finish_btn.clicked.connect(self._finish)
        hdr.addWidget(self._finish_btn)
        root.addLayout(hdr)
        root.addWidget(separator())

        # Chat
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._chat_widget = QWidget()
        self._chat_lay = QVBoxLayout(self._chat_widget)
        self._chat_lay.setSpacing(6)
        self._chat_lay.addStretch()
        scroll.setWidget(self._chat_widget)
        self._scroll = scroll
        root.addWidget(scroll, 1)

        # Hint
        self._hint_label = make_label("", color="#0078d4", size=12)
        self._hint_label.setWordWrap(True)
        self._hint_label.hide()
        root.addWidget(self._hint_label)

        # Input
        inp_row = QHBoxLayout()
        self._input = QTextEdit()
        self._input.setFixedHeight(64)
        self._input.setStyleSheet("QTextEdit { border: 1px solid #ccc; border-radius: 4px; padding: 6px; font-size: 13px; }"
                                  "QTextEdit:focus { border-color: #0078d4; }")
        self._input.setPlaceholderText("Введи сообщение...")
        inp_row.addWidget(self._input)
        self._send_btn = make_button("Отправить")
        self._send_btn.setFixedWidth(100)
        self._send_btn.clicked.connect(self._send)
        inp_row.addWidget(self._send_btn)
        root.addLayout(inp_row)

    def load(self, session_id, scenario, dialog_type, difficulty):
        self._session_id = session_id
        self._difficulty = difficulty
        self._hdr_label.setText(f"{scenario['title']}  |  {dialog_type} / {difficulty}")
        # Clear chat
        while self._chat_lay.count() > 1:
            item = self._chat_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._hint_label.hide()
        # Load existing messages
        run_worker(self, lambda: api.get_messages(session_id), self._render_history)

    def _render_history(self, data):
        for msg in data.get("messages", []):
            self._add_bubble(msg["content"], msg["role"] == "user", msg.get("hint"))

    def _add_bubble(self, text, is_user, hint=None):
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(420)
        bubble.setStyleSheet(
            f"background: {'#0078d4' if is_user else '#f0f0f0'}; "
            f"color: {'white' if is_user else '#1a1a1a'}; "
            "border-radius: 10px; padding: 8px 12px; font-size: 13px;"
        )
        bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        align = Qt.AlignRight if is_user else Qt.AlignLeft
        self._chat_lay.insertWidget(self._chat_lay.count() - 1, bubble, alignment=align)

        if hint:
            h = make_label(f"💡 {hint}", color="#0078d4", size=12)
            h.setWordWrap(True)
            self._chat_lay.insertWidget(self._chat_lay.count() - 1, h, alignment=Qt.AlignLeft)

        # Scroll to bottom
        self._scroll.verticalScrollBar().setValue(self._scroll.verticalScrollBar().maximum())

    def _send(self):
        text = self._input.toPlainText().strip()
        if not text or not self._session_id:
            return
        self._input.clear()
        self._add_bubble(text, is_user=True)
        self._send_btn.setEnabled(False)
        self._input.setEnabled(False)

        def fn():
            return api.send_message(self._session_id, text)

        def done(data):
            self._send_btn.setEnabled(True)
            self._input.setEnabled(True)
            self._add_bubble(data["assistant_message"], is_user=False, hint=data.get("hint"))

        def err(e):
            self._send_btn.setEnabled(True)
            self._input.setEnabled(True)
            QMessageBox.warning(self, "Ошибка", e)

        run_worker(self, fn, done, err)

    def _finish(self):
        self._finish_btn.setEnabled(False)
        run_worker(self, lambda: api.finish_session(self._session_id),
                   self.finished.emit,
                   lambda e: (self._finish_btn.setEnabled(True), QMessageBox.warning(self, "Ошибка", e)))

    def _confirm_back(self):
        reply = QMessageBox.question(self, "Выйти?", "Сессия будет прервана. Продолжить?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.back.emit()


class ResultScreen(QWidget):
    to_scenarios = Signal()

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        box = QWidget()
        box.setFixedWidth(420)
        lay = QVBoxLayout(box)
        lay.setSpacing(10)

        lay.addWidget(make_label("Результаты сессии", bold=True, size=18))
        lay.addWidget(separator())

        self._result_lbl = make_label("", bold=True, size=16)
        lay.addWidget(self._result_lbl)

        self._goal_box = QGroupBox("Оценка цели")
        gb = QVBoxLayout(self._goal_box)
        self._goal_lbl = QLabel()
        self._goal_lbl.setWordWrap(True)
        self._goal_lbl.setStyleSheet("font-size: 13px;")
        gb.addWidget(self._goal_lbl)
        lay.addWidget(self._goal_box)

        self._err_box = QGroupBox("Разбор ошибок")
        eb = QVBoxLayout(self._err_box)
        self._err_lbl = QLabel()
        self._err_lbl.setWordWrap(True)
        self._err_lbl.setStyleSheet("font-size: 13px;")
        eb.addWidget(self._err_lbl)
        lay.addWidget(self._err_box)

        self._lvl_lbl = make_label("", color="#0078d4", bold=True)
        lay.addWidget(self._lvl_lbl)

        btn = make_button("К сценариям")
        btn.clicked.connect(self.to_scenarios.emit)
        lay.addWidget(btn)

        root.addWidget(box, alignment=Qt.AlignCenter)

    def load(self, data):
        result = data.get("result")
        if result == "success":
            self._result_lbl.setText("✅ Цель достигнута!")
            self._result_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #107c10;")
        elif result == "fail":
            self._result_lbl.setText("❌ Цель не достигнута")
            self._result_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #d83b01;")
        else:
            self._result_lbl.setText("✔ Сессия завершена")
            self._result_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #555;")

        goal = data.get("goal_feedback")
        if goal:
            self._goal_lbl.setText(goal)
            self._goal_box.show()
        else:
            self._goal_box.hide()

        errors = data.get("errors_summary")
        if errors:
            self._err_lbl.setText(errors)
            self._err_box.show()
        else:
            self._err_box.hide()

        if data.get("level_up_recommended"):
            self._lvl_lbl.setText("🎉 Попробуй повысить уровень в настройках!")
        else:
            self._lvl_lbl.setText("")


class HistoryScreen(QWidget):
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.addWidget(make_label("История сессий", bold=True, size=16))
        hdr.addStretch()
        ref = make_button("Обновить", primary=False, small=True)
        ref.clicked.connect(self.load)
        hdr.addWidget(ref)
        root.addLayout(hdr)
        root.addWidget(separator())

        self._list = QListWidget()
        self._list.setStyleSheet("QListWidget { border: none; } QListWidgetItem { padding: 6px; }")
        root.addWidget(self._list)

    def load(self):
        run_worker(self, lambda: api.sessions(limit=50), self._render)

    def _render(self, data):
        self._list.clear()
        for s in data.get("sessions", []):
            started = s["started_at"][:10] if s["started_at"] else "—"
            result = s.get("result") or "—"
            status = s["status"]
            text = f"{started}  |  {s['dialog_type']} / {s['difficulty']}  |  {status}  |  {result}"
            self._list.addItem(QListWidgetItem(text))


class SettingsScreen(QWidget):
    logout = Signal()

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignTop)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        root.addWidget(make_label("Настройки", bold=True, size=16))
        root.addWidget(separator())

        self._info = make_label("", color="#555")
        root.addWidget(self._info)

        root.addWidget(make_label("Язык интерфейса"))
        self._iface = make_combo(["Русский (ru)", "English (en)"])
        root.addWidget(self._iface)

        root.addWidget(make_label("Изучаемый язык"))
        self._target = make_combo(["English (en)", "Русский (ru)"])
        root.addWidget(self._target)

        root.addWidget(make_label("Уровень владения"))
        self._level = make_combo(["A1", "A2", "B1", "B2", "C1", "C2"])
        root.addWidget(self._level)

        root.addWidget(make_label("Возрастная группа"))
        self._age = make_combo(["Взрослый (adult)", "Подросток (teen)"])
        root.addWidget(self._age)

        save_btn = make_button("Сохранить")
        save_btn.clicked.connect(lambda: self._save(save_btn))
        root.addWidget(save_btn)

        root.addSpacing(16)
        logout_btn = make_button("Выйти из аккаунта", primary=False)
        logout_btn.clicked.connect(self._logout)
        root.addWidget(logout_btn)

    def load(self, profile):
        self._info.setText(f"{profile['username']}  ·  {profile['email']}")
        self._iface.setCurrentIndex(0 if profile.get("interface_language") == "ru" else 1)
        self._target.setCurrentIndex(0 if profile.get("target_language") == "en" else 1)
        lvl = profile.get("lang_level", "A1")
        self._level.setCurrentIndex(["A1", "A2", "B1", "B2", "C1", "C2"].index(lvl))
        self._age.setCurrentIndex(0 if profile.get("age_group") == "adult" else 1)

    def _save(self, btn):
        iface = "ru" if self._iface.currentIndex() == 0 else "en"
        target = "en" if self._target.currentIndex() == 0 else "ru"
        level = self._level.currentText()
        age = "adult" if self._age.currentIndex() == 0 else "teen"
        run_worker(self, lambda: api.update_me(interface_language=iface, target_language=target,
                                               lang_level=level, age_group=age),
                   lambda _: QMessageBox.information(self, "Сохранено", "Профиль обновлён"), btn=btn)

    def _logout(self):
        reply = QMessageBox.question(self, "Выйти?", "Вы уверены?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            Worker(api.logout).start()
            QSettings("Rolingo", "Desktop").remove("refresh_token")
            self.logout.emit()


# ── MAIN WINDOW ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rolingo")
        self.resize(800, 580)
        self._profile = None
        self._current_scenario = None
        self._build()
        self._try_autologin()

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self._sidebar = QWidget()
        self._sidebar.setFixedWidth(160)
        self._sidebar.setStyleSheet("background: #f3f3f3; border-right: 1px solid #e0e0e0;")
        sb = QVBoxLayout(self._sidebar)
        sb.setContentsMargins(0, 8, 0, 8)
        sb.setSpacing(2)

        self._nav_btns = {}
        nav_items = [("scenarios", "🎭  Сценарии"), ("history", "📋  История"), ("settings", "⚙️  Настройки")]
        for key, label in nav_items:
            btn = QPushButton(label)
            btn.setFixedHeight(40)
            btn.setStyleSheet(
                "QPushButton { text-align: left; padding-left: 16px; border: none; background: transparent; font-size: 13px; }"
                "QPushButton:hover { background: #e0e0e0; }"
                "QPushButton[active=true] { background: #dce6f5; color: #0078d4; font-weight: bold; }"
            )
            btn.clicked.connect(lambda _, k=key: self._nav(k))
            sb.addWidget(btn)
            self._nav_btns[key] = btn

        sb.addStretch()
        root.addWidget(self._sidebar)
        self._sidebar.hide()

        # Stack
        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        self._auth = AuthScreen()
        self._auth.logged_in.connect(self._on_login)
        self._stack.addWidget(self._auth)

        self._onboarding = OnboardingScreen()
        self._onboarding.done.connect(self._on_onboarding_done)
        self._stack.addWidget(self._onboarding)

        self._scenarios = ScenariosScreen()
        self._scenarios.start_session.connect(self._start_session)
        self._stack.addWidget(self._scenarios)

        self._session = SessionScreen()
        self._session.finished.connect(self._on_session_finished)
        self._session.back.connect(lambda: self._nav("scenarios"))
        self._stack.addWidget(self._session)

        self._result = ResultScreen()
        self._result.to_scenarios.connect(lambda: self._nav("scenarios"))
        self._stack.addWidget(self._result)

        self._history = HistoryScreen()
        self._stack.addWidget(self._history)

        self._settings = SettingsScreen()
        self._settings.logout.connect(self._on_logout)
        self._stack.addWidget(self._settings)

    def _try_autologin(self):
        settings = QSettings("Rolingo", "Desktop")
        rt = settings.value("refresh_token")
        if not rt:
            self._stack.setCurrentWidget(self._auth)
            return

        def fn():
            import httpx as _httpx
            r = _httpx.post(f"{BASE_URL}/auth/refresh", json={"refresh_token": rt}, timeout=10)
            if not r.is_success:
                raise ApiError("Token expired")
            return r.json()

        def done(data):
            api.set_tokens(data["access_token"], data["refresh_token"])
            settings.setValue("refresh_token", data["refresh_token"])
            self._on_login()

        def err(_):
            settings.remove("refresh_token")
            self._stack.setCurrentWidget(self._auth)

        run_worker(self, fn, done, err)

    def _on_login(self):
        run_worker(self, api.me, self._check_onboarding)

    def _check_onboarding(self, profile):
        self._profile = profile
        if not profile.get("onboarding_completed"):
            self._stack.setCurrentWidget(self._onboarding)
        else:
            self._show_main()

    def _on_onboarding_done(self):
        run_worker(self, api.me, lambda p: (setattr(self, '_profile', p), self._show_main()))

    def _show_main(self):
        self._sidebar.show()
        self._nav("scenarios")

    def _nav(self, key):
        for k, btn in self._nav_btns.items():
            btn.setProperty("active", k == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if key == "scenarios":
            self._stack.setCurrentWidget(self._scenarios)
            self._scenarios.load()
        elif key == "history":
            self._stack.setCurrentWidget(self._history)
            self._history.load()
        elif key == "settings":
            self._stack.setCurrentWidget(self._settings)
            if self._profile:
                self._settings.load(self._profile)

    def _start_session(self, scenario, dialog_type, difficulty):
        self._current_scenario = scenario

        def fn():
            return api.create_session(scenario["id"], dialog_type, difficulty)

        def done(data):
            session_id = data["id"]
            self._stack.setCurrentWidget(self._session)
            self._session.load(session_id, scenario, dialog_type, difficulty)

        run_worker(self, fn, done)

    def _on_session_finished(self, data):
        self._stack.setCurrentWidget(self._result)
        self._result.load(data)

    def _on_logout(self):
        self._profile = None
        self._sidebar.hide()
        self._stack.setCurrentWidget(self._auth)


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Rolingo")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#ffffff"))
    palette.setColor(QPalette.WindowText, QColor("#1a1a1a"))
    app.setPalette(palette)

    font = QFont("Segoe UI", 10) if sys.platform == "win32" else QFont("SF Pro Text", 10)
    app.setFont(font)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
