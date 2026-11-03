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


# Проверка класса
if __name__ == "__main__":
    student = Student("Тестовый ученик")

    print("ФИО:", student.full_name)
    print("В архиве:", student.is_archived)

    student.archive()
    print("После архивирования:", student.is_archived)

    student.restore()
    print("После восстановления:", student.is_archived)