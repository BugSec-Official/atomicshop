import msvcrt


# === WINDOWS ONLY FUNCTIONS ===========================================================================================
def wait_any_key(prompt="Press any key to continue..."):
    print(prompt, end="", flush=True)
    msvcrt.getch()  # waits for one key press (no Enter needed)
    print()         # move to next line
# === EOF WINDOWS ONLY FUNCTIONS =======================================================================================