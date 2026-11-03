"""Данные учеников."""


class Student:
    """Данные одного ученика."""

    def __init__(
        self,
        full_name,
        student_id=None,
        phone=None,
        messenger_type=None,
        messenger_contact=None,
        is_archived=False
    ):
        """Заполнение данных ученика."""
        full_name = full_name.strip()

        if full_name == "":
            raise ValueError("ФИО ученика не должно быть пустым.")

        self.student_id = student_id
        self.full_name = full_name
        self.phone = phone
        self.messenger_type = messenger_type
        self.messenger_contact = messenger_contact
        self.is_archived = is_archived

    def archive(self):
        """Перемещение в архив."""
        self.is_archived = True

    def restore(self):
        """Восстановление из архива."""
        self.is_archived = False

class Parent:
    """Данные родителя."""

    def __init__(
        self,
        full_name,
        parent_id=None,
        phone=None,
        messenger_type=None,
        messenger_contact=None
    ):
        """Заполнение данных родителя."""
        full_name = full_name.strip()

        if full_name == "":
            raise ValueError("ФИО родителя не должно быть пустым.")

        self.parent_id = parent_id
        self.full_name = full_name
        self.phone = phone
        self.messenger_type = messenger_type
        self.messenger_contact = messenger_contact


class Enrollment:
    """Направление обучения ученика."""

    def __init__(
        self,
        student_id,
        subject_id,
        preparation_goal,
        price_60_kopecks,
        enrollment_id=None
    ):
        """Предмет, цель подготовки и цена."""
        if (
            not isinstance(price_60_kopecks, int)
            or isinstance(price_60_kopecks, bool)
            or price_60_kopecks < 0
        ):
            raise ValueError("Цена должна быть целым числом копеек от 0.")

        self.enrollment_id = enrollment_id
        self.student_id = student_id
        self.subject_id = subject_id
        self.price_60_kopecks = price_60_kopecks
        self.change_goal(preparation_goal)

    def change_goal(self, goal):
        """Изменение цели подготовки."""
        goal = goal.strip()

        if goal == "":
            raise ValueError("Цель подготовки не должна быть пустой.")

        self.preparation_goal = goal

    def calculate_price(self, duration_minutes):
        """Стоимость занятия в копейках."""
        if (
            not isinstance(duration_minutes, int)
            or isinstance(duration_minutes, bool)
            or duration_minutes <= 0
            or duration_minutes % 30 != 0
        ):
            raise ValueError(
                "Нужно целое число минут, больше 0 и кратное 30."
            )

        # Округление до целой копейки
        total = self.price_60_kopecks * duration_minutes
        return (total + 30) // 60
# Проверка класса
if __name__ == "__main__":
    student = Student("Тестовый ученик")

    print("ФИО:", student.full_name)
    print("В архиве:", student.is_archived)

    student.archive()
    print("После архивирования:", student.is_archived)

    student.restore()
    print("После восстановления:", student.is_archived)
    parent = Parent("Тестовый родитель")
    print("Родитель:", parent.full_name)

    enrollment = Enrollment(
        student_id=1,
        subject_id=1,
        preparation_goal="ЕГЭ",
        price_60_kopecks=140000
    )

    print("30 минут:", enrollment.calculate_price(30), "коп.")
    print("90 минут:", enrollment.calculate_price(90), "коп.")