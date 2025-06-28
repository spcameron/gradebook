# main.py

from models.student import Student


def main():
    print("Running main.py")
    s = Student("s001", "Sean", "scameron@mmm.edu")
    print(s.to_dict())


if __name__ == "__main__":
    main()
