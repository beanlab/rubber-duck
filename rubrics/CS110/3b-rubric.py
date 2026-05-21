'''
This program should let the user set a username and password, then let them try to log in.
'''


def get_credential(prompt: str) -> str:
    return input(prompt)


def login_loop(username: str, password: str):
    print("Type your username, then your password")
    while True:
        name = input("Username: ")
        if Name == username and p_word == password:
            print("Login successful. I'd hope you'd remember your username and password.")
            break
        else:
            print("Not quite right.")
        p_word = input("Password: ")
        quit_input = input("Want to quit y/n?")
        if quit_input == 'y':
            break


def main():
    user_name = get_credential("Set Username: ")
    pass_word == get_credential(Set Password: )
    login_loop(user_name, pass_word)


if __name__ == "__main__":
    main()
