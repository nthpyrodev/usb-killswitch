
# USB Kill Switch

This project is designed for whistleblowers/journalists in oppressive regimes. Please keep in mind that the Linux version is not ready, so stick with the Windows version for now. It would be great if anyone could contribute to this project though!

Linux is not fully supported yet.

## How to run

Prerequisites:

- Python installed
- These modules installed: `tkinter subprocess threading time platform os sys types` Note that most of these modules should be there by default
- Admin access to the computer

First option:
Put the Python script onto the designated USB. This script is loaded into RAM, so that once armed, if the designated USB containing the script is pulled out, then the killswitches can still activate.

Second option:
Put the Python script anywhere you want. It will detect any type of change, whether it be storage, periphals, etc, and trigger the killswitches. This is useful if a mouse jiggler is inserted to keep the computer awake.
## Features


- Dismount VeraCrypt volumes
- End specified processes
- Delete or overwrite specified files
- Turn off screen
- Lock OS
- Shutdown
- Execute custom commands such as `python3 something.py` or any command that can be run on Windows
- Trigger killswitch on specified USB pull
- Trigger killswitch on any device change
- Button must be pressed 5 times to disarm any killswitch, to avoid accidental presses.
- Log for viewing changes.
## Notes

If the killswitch gets triggered, then you must disarm then rearm again to reactivate it.

# Contributing

Contributors are welcome, even if the changes are minor, or even just improving the ReadMe.


![image](https://github.com/user-attachments/assets/d6c5d20b-e791-4cc7-b974-ed07a69ac433)
![image](https://github.com/user-attachments/assets/3a292a4a-599e-4b42-a642-0a98b7ccc008)


