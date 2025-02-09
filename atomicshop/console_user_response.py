import sys


def query_positive_negative(
        question_string: str,
        add_first_values_to_question: bool = True,
        positive_answers: list = None,
        negative_answers: list = None
) -> bool:
    """
    Ask for "yes" / "no" input to a question that is passed as a "question_string".
    Returns 'True' for 'positive' answers and 'False' for 'negative' answers.

    :param question_string: Question that user will be asked.
    :param add_first_values_to_question: Boolean that sets if ' [y/n]' string will be added to the question.
    :param positive_answers: A list of non default positive answers can be passed.
        Since it is not recommended passing mutable objects (list) as default, it is set to 'None' and later assigned
        default values.
    :param negative_answers: A list of non default negative answers can be passed.
        Since it is not recommended passing mutable objects (list) as default, it is set to 'None' and later assigned
        default values.
    :return: Boolean that depend, if user answered yes or no.
    """

    # If default 'None' was assigned, the get the default answers.
    if not positive_answers:
        positive_answers = ['y', 'yes', '']
    if not negative_answers:
        negative_answers = ['n', 'no']

    # If 'add_yes_no_string' was set to 'True', we'll add the string to the question.
    if add_first_values_to_question:
        question_string = f'{question_string} [{positive_answers[0]}/{negative_answers[0]}]'

    # As long as "right_answer" is False the loop will execute again
    while True:
        # Print the passed question
        print(question_string)
        # Get the input from the console in lowercase
        choice = input().lower()

        # If the gathered value is in "Yes" answers array
        if choice in positive_answers:
            # Function will return True
            return True
        # Else If the gathered value is in "No" answers array
        elif choice in negative_answers:
            # Function will return False
            return False
        # If the gathered input is not in the arrays
        else:
            # Then output to console the message
            print("Please respond with either:", positive_answers, negative_answers)


def do_you_want_to_continue_yn(message: str) -> None:
    """
    Function passes the question to 'query_yesno' function to ask the user what to do.
    If the user doesn't want to continue, the script exits.

    :param message: Message to ask the user.
    :return: None
    """

    if not query_positive_negative(message):
        print('Exiting...')
        sys.exit()
