"""Главное окно программы."""

import tkinter as tk
from tkinter import font


class MainWindow(tk.Frame):
    """Меню и рабочая область."""

    def __init__(self, parent):
        """Создание главного окна."""
        super().__init__(parent, bg="white")
        self.before_change = None
        self.current_page = None

        if "Inter" in font.families(parent):
            self.family = "Inter"
        else:
            self.family = "Arial"

        title = tk.Label(
            self,
            text="ИС Репетитор",
            font=(self.family, -24),
            bg="white",
            fg="black",
            borderwidth=0
        )
        title.place(relx=0.5, y=0, anchor="n", height=30)

        self.content = tk.Frame(
            self,
            bg="#d9d9d9",
            highlightbackground="black",
            highlightthickness=1
        )
        self.content.place(
            x=36, y=76,
            relwidth=1, width=-80,
            relheight=1, height=-116
        )

        tabs = [
            ("Расписание", 36, 162),
            ("Ученики", 214, 142),
            ("Занятия", 356, 142),
            ("Оплаты", 511, 119),
            ("Отчеты", 646, 120),
            ("Настройки", 780, 170)
        ]

        self.buttons = {}
        self.pages = {}

        for name, x, width in tabs:
            button = tk.Button(
                self,
                text=name,
                font=(self.family, -24),
                bg="white",
                fg="black",
                activebackground="#d9d9d9",
                activeforeground="black",
                relief="flat",
                borderwidth=0,
                highlightthickness=0,
                cursor="hand2",
                command=lambda page=name: self.show_page(page)
            )
            button.place(x=x, y=33, width=width, height=43)
            self.buttons[name] = button

            page = tk.Frame(self.content, bg="#d9d9d9")
            self.pages[name] = page

        self.show_page("Расписание")

    def show_page(self, name):
        """Переход между вкладками."""
        if self.before_change is not None and name != self.current_page:
            if not self.before_change(name):
                return False
        for page_name in self.pages:
            self.pages[page_name].pack_forget()
            self.buttons[page_name].configure(
                bg="white",
                relief="flat",
                borderwidth=0
            )

        self.pages[name].pack(fill="both", expand=True)
        self.buttons[name].configure(
            bg="#d9d9d9",
            relief="solid",
            borderwidth=1
        )
        self.current_page = name
        return True
