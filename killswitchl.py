import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import threading
import time
import platform
import os
import sys

class USBMonitor:
    def __init__(self, selected_tasks, custom_commands, file_to_delete, process_to_kill):
        self.usb_label = "K"  # Default K label set here
        self.selected_tasks = selected_tasks
        self.custom_commands = custom_commands
        self.file_to_delete = file_to_delete
        self.process_to_kill = process_to_kill
        self.monitoring = False
        self.usb_monitoring = False
        self.os_type = platform.system()
        self.usb_devices = self.get_current_usb_devices()
        self.pause_counter = 0
        self.usb_pause_counter = 0
        self.k_removed = False
        self.desktop_env = self.detect_desktop_environment()

    def detect_desktop_environment(self):
        # Check various environment variables to detect the desktop environment
        env = os.environ.get('XDG_CURRENT_DESKTOP')
        if not env:
            env = os.environ.get('DESKTOP_SESSION')
        if not env:
            env = os.environ.get('GNOME_DESKTOP_SESSION_ID')
            if env:
                return 'gnome'
        if not env:
            env = os.environ.get('MATE_DESKTOP_SESSION_ID')
            if env:
                return 'mate'
        if not env:
            env = os.environ.get('CINNAMON_VERSION')
            if env:
                return 'cinnamon'
        if env:
            env = env.lower()
            if 'gnome' in env:
                return 'gnome'
            elif 'kde' in env or 'plasma' in env:
                return 'kde'
            elif 'xfce' in env:
                return 'xfce'
            elif 'lxde' in env:
                return 'lxde'
            elif 'lxqt' in env:
                return 'lxqt'
            elif 'mate' in env:
                return 'mate'
            elif 'cinnamon' in env:
                return 'cinnamon'
            elif 'sway' in env:
                return 'sway'
            elif 'i3' in env:
                return 'i3'
            elif 'deepin' in env:
                return 'deepin'
            elif 'enlightenment' in env:
                return 'enlightenment'
            elif 'pantheon' in env:
                return 'pantheon'
        # Fallback to checking for specific processes
        if subprocess.run(["pgrep", "-x", "gnome-shell"], capture_output=True).returncode == 0:
            return 'gnome'
        if subprocess.run(["pgrep", "-x", "kdeinit5"], capture_output=True).returncode == 0:
            return 'kde'
        if subprocess.run(["pgrep", "-x", "xfce4-session"], capture_output=True).returncode == 0:
            return 'xfce'
        if subprocess.run(["pgrep", "-x", "lxsession"], capture_output=True).returncode == 0:
            return 'lxde'
        if subprocess.run(["pgrep", "-x", "lxqt-session"], capture_output=True).returncode == 0:
            return 'lxqt'
        if subprocess.run(["pgrep", "-x", "mate-session"], capture_output=True).returncode == 0:
            return 'mate'
        if subprocess.run(["pgrep", "-x", "cinnamon"], capture_output=True).returncode == 0:
            return 'cinnamon'
        if subprocess.run(["pgrep", "-x", "sway"], capture_output=True).returncode == 0:
            return 'sway'
        if subprocess.run(["pgrep", "-x", "i3"], capture_output=True).returncode == 0:
            return 'i3'
        return 'unknown'

    def get_current_usb_devices(self):
        devices = []
        if self.os_type == "Linux":
            result = subprocess.run(["lsusb"], capture_output=True, text=True)
            if result.returncode == 0:
                devices = result.stdout.splitlines()
        return devices

    def check_usb_changes(self):
        current_devices = self.get_current_usb_devices()
        if set(current_devices) != set(self.usb_devices):
            self.usb_devices = current_devices
            return True
        return False

    def check_k_label_usb_presence(self):
        if self.os_type == "Linux":
            return os.path.ismount(f"/media/{self.usb_label}")
        return False

    def dismount_veracrypt_volumes(self):
        subprocess.run(["veracrypt", "-d"], shell=True)

    def kill_process(self):
        if self.process_to_kill:
            result = subprocess.run(["pkill", "-f", self.process_to_kill], capture_output=True)
            if result.returncode != 0:
                self.log_message(f"Failed to terminate process: {result.stderr.decode()}")
            else:
                self.log_message("Process terminated successfully.")

    def shutdown_system(self):
        shutdown_cmds = {
            "gnome": ["gnome-session-quit", "--no-prompt"],
            "kde": ["qdbus", "org.kde.ksmserver", "/KSMServer", "logout", "0", "3", "3"],
            "xfce": ["xfce4-session-logout", "--logout"],
            "lxde": ["lxde-logout"],
            "lxqt": ["lxqt-leave", "--logout"],
            "mate": ["mate-session-save", "--shutdown-dialog"],
            "cinnamon": ["cinnamon-session-quit", "--no-prompt"],
            "i3": ["i3-msg", "exit"],
            "sway": ["swaymsg", "exit"],
            "deepin": ["dbus-send", "--system", "--print-reply", "--dest=org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager.PowerOff", "boolean:true"],
            "enlightenment": ["enlightenment_remote", "-shutdown"],
            "pantheon": ["io.elementary.greeter", "--shutdown"]
        }

        cmd = shutdown_cmds.get(self.desktop_env, ["shutdown", "now"])
        try:
            subprocess.run(cmd, shell=True)
        except Exception as e:
            self.log_message(f"Failed to shutdown system: {str(e)}")

    def delete_files(self):
        file_paths = self.file_to_delete.split("; ")
        for file_path in file_paths:
            if file_path:
                try:
                    absolute_file_path = os.path.abspath(file_path)
                    if os.path.isfile(absolute_file_path):
                        result = subprocess.run(["rm", absolute_file_path], shell=True, capture_output=True)
                        if result.returncode != 0:
                            self.log_message(f"Failed to delete file: {result.stderr.decode()}")
                        else:
                            self.log_message("File deleted successfully.")
                    else:
                        self.log_message(f"File not found: {absolute_file_path}")
                except Exception as e:
                    self.log_message(f"Error deleting file: {e}")

    def overwrite_files(self):
        file_paths = self.file_to_delete.split("; ")
        for file_path in file_paths:
            if file_path:
                try:
                    absolute_file_path = os.path.abspath(file_path)
                    if os.path.isfile(absolute_file_path):
                        result = subprocess.run(["shred", "-u", absolute_file_path], shell=True, capture_output=True)
                        if result.returncode != 0:
                            self.log_message(f"Failed to overwrite file: {result.stderr.decode()}")
                        else:
                            self.log_message("File overwritten successfully.")
                    else:
                        self.log_message(f"File not found: {absolute_file_path}")
                except Exception as e:
                    self.log_message(f"Error overwriting file: {e}")

    def turn_off_screen(self):
        subprocess.run(["xset", "dpms", "force", "off"], shell=True)

    def lock_computer(self):
        lock_cmds = {
            "gnome": ["gnome-screensaver-command", "-l"],
            "kde": ["qdbus", "org.freedesktop.ScreenSaver", "/ScreenSaver", "Lock"],
            "xfce": ["xflock4"],
            "lxde": ["lxlock"],
            "lxqt": ["lxqt-leave", "--lock"],
            "mate": ["mate-screensaver-command", "-l"],
            "cinnamon": ["cinnamon-screensaver-command", "-l"],
            "i3": ["i3lock"],
            "sway": ["swaylock"],
            "deepin": ["dbus-send", "--system", "--print-reply", "--dest=org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager.Lock"],
            "enlightenment": ["enlightenment_remote", "-lock"],
            "pantheon": ["io.elementary.greeter", "--lock"],
            "xscreensaver": ["xscreensaver-command", "-lock"]
        }

        cmd = lock_cmds.get(self.desktop_env, ["xset", "dpms", "force", "off"])
        try:
            subprocess.run(cmd, shell=True)
        except Exception as e:
            self.log_message(f"Failed to lock computer: {str(e)}")

    def start_monitoring(self):
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor)
            self.monitor_thread.start()

    def start_usb_monitoring(self):
        if not self.usb_monitoring:
            self.usb_monitoring = True
            self.usb_monitor_thread = threading.Thread(target=self.usb_monitor)
            self.usb_monitor_thread.start()

    def monitor(self):
        while self.monitoring:
            if self.pause_counter > 0:
                self.pause_counter -= 1
                time.sleep(1)
                continue
            if self.check_usb_changes():
                self.execute_tasks()
            time.sleep(2)

    def usb_monitor(self):
        while self.usb_monitoring:
            if self.usb_pause_counter > 0:
                self.usb_pause_counter -= 1
                time.sleep(1)
                continue
            k_present = self.check_k_label_usb_presence()
            if not k_present:
                if not self.k_removed:
                    self.k_removed = True
                    self.execute_tasks()
            else:
                self.k_removed = False
            time.sleep(2)

    def execute_tasks(self):
        if "Dismount VeraCrypt Volumes" in self.selected_tasks:
            self.dismount_veracrypt_volumes()
        if "End Process" in self.selected_tasks:
            self.kill_process()
        if "Delete File" in self.selected_tasks:
            self.delete_files()
        if "Overwrite File" in self.selected_tasks:
            self.overwrite_files()
        if "Turn Off Screen" in self.selected_tasks:
            self.turn_off_screen()
        if "Lock Computer" in self.selected_tasks:
            self.lock_computer()
        if "Shutdown" in self.selected_tasks:
            self.shutdown_system()
        for cmd in self.custom_commands:
            if cmd:
                try:
                    subprocess.run(cmd, shell=True)
                except Exception as e:
                    self.log_message(f"Error executing custom command: {e}")

    def toggle_pause(self):
        if self.monitoring:
            self.pause_counter = 5

    def toggle_usb_pause(self):
        if self.usb_monitoring:
            self.usb_pause_counter = 5

    def log_message(self, message):
        log_text.config(state=tk.NORMAL)
        log_text.insert(tk.END, message + "\n")
        log_text.config(state=tk.DISABLED)
        log_text.see(tk.END)

def on_start_button_click():
    selected_tasks = [task.get() for task in tasks if task.get()]
    if not selected_tasks:
        messagebox.showerror("Error", "Please select at least one task")
        return
    custom_commands = [command_entry1.get(), command_entry2.get(), command_entry3.get()]
    file_to_delete = file_entry.get()
    process_to_kill = process_entry.get()
    if usb_monitor.monitoring:
        messagebox.showinfo("Monitoring", "Monitoring already started")
        return
    usb_monitor.selected_tasks = selected_tasks
    usb_monitor.custom_commands = custom_commands
    usb_monitor.file_to_delete = file_to_delete
    usb_monitor.process_to_kill = process_to_kill
    usb_monitor.start_monitoring()
    start_button.config(state=tk.DISABLED)
    pause_button.config(state=tk.NORMAL)
    status_label.config(text="Monitoring started...", fg="green")

def on_pause_button_click():
    usb_monitor.toggle_pause()
    status_label.config(text="Monitoring paused...", fg="orange")

def on_usb_start_button_click():
    selected_tasks = [task.get() for task in tasks if task.get()]
    if not selected_tasks:
        messagebox.showerror("Error", "Please select at least one task")
        return
    custom_commands = [command_entry1.get(), command_entry2.get(), command_entry3.get()]
    file_to_delete = file_entry.get()
    process_to_kill = process_entry.get()
    if usb_monitor.usb_monitoring:
        messagebox.showinfo("Monitoring", "USB Monitoring already started")
        return
    usb_monitor.selected_tasks = selected_tasks
    usb_monitor.custom_commands = custom_commands
    usb_monitor.file_to_delete = file_to_delete
    usb_monitor.process_to_kill = process_to_kill
    usb_monitor.start_usb_monitoring()
    usb_start_button.config(state=tk.DISABLED)
    usb_pause_button.config(state=tk.NORMAL)
    usb_status_label.config(text="USB Monitoring started...", fg="green")

def on_usb_pause_button_click():
    usb_monitor.toggle_usb_pause()
    usb_status_label.config(text="USB Monitoring paused...", fg="orange")

def log_message(message):
    log_text.config(state=tk.NORMAL)
    log_text.insert(tk.END, message + "\n")
    log_text.config(state=tk.DISABLED)
    log_text.see(tk.END)

def select_files():
    file_paths = filedialog.askopenfilenames(title="Select files")
    file_entry.delete(0, tk.END)
    file_entry.insert(0, "; ".join(file_paths))

# Create the main application window
root = tk.Tk()
root.title("USB Monitor")

# Task selection
task_frame = tk.LabelFrame(root, text="Tasks", padx=10, pady=10)
task_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
tasks = [
    tk.StringVar(value="Dismount VeraCrypt Volumes"),
    tk.StringVar(value="End Process"),
    tk.StringVar(value="Delete File"),
    tk.StringVar(value="Overwrite File"),
    tk.StringVar(value="Turn Off Screen"),
    tk.StringVar(value="Lock Computer"),
    tk.StringVar(value="Shutdown")
]
for i, task in enumerate(tasks):
    tk.Checkbutton(task_frame, text=task.get(), variable=task, onvalue=task.get(), offvalue="").grid(row=i, column=0, sticky="w")

# File deletion
file_frame = tk.LabelFrame(root, text="Files to delete", padx=10, pady=10)
file_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
file_entry = tk.Entry(file_frame, width=50)
file_entry.grid(row=0, column=0, padx=10, pady=5)
select_button = tk.Button(file_frame, text="Select Files", command=select_files)
select_button.grid(row=0, column=1, padx=10, pady=5)

# Process to kill
process_frame = tk.LabelFrame(root, text="Process to kill", padx=10, pady=10)
process_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
process_entry = tk.Entry(process_frame, width=50)
process_entry.grid(row=0, column=0, padx=10, pady=5)

# Custom commands
command_frame = tk.LabelFrame(root, text="Custom commands", padx=10, pady=10)
command_frame.grid(row=2, column=1, padx=10, pady=10, sticky="nsew")
command_entry1 = tk.Entry(command_frame, width=50)
command_entry1.grid(row=0, column=0, padx=10, pady=5)
command_entry2 = tk.Entry(command_frame, width=50)
command_entry2.grid(row=1, column=0, padx=10, pady=5)
command_entry3 = tk.Entry(command_frame, width=50)
command_entry3.grid(row=2, column=0, padx=10, pady=5)

# Control buttons
button_frame = tk.Frame(root)
button_frame.grid(row=3, column=0, columnspan=2, pady=10)
start_button = tk.Button(button_frame, text="Start Monitoring", command=on_start_button_click)
start_button.grid(row=0, column=0, padx=5)
pause_button = tk.Button(button_frame, text="Pause Monitoring", command=on_pause_button_click)
pause_button.grid(row=0, column=1, padx=5)
pause_button.config(state=tk.DISABLED)
usb_start_button = tk.Button(button_frame, text="Start USB Monitoring", command=on_usb_start_button_click)
usb_start_button.grid(row=0, column=2, padx=5)
usb_pause_button = tk.Button(button_frame, text="Pause USB Monitoring", command=on_usb_pause_button_click)
usb_pause_button.grid(row=0, column=3, padx=5)
usb_pause_button.config(state=tk.DISABLED)

# Status labels
status_label = tk.Label(root, text="Monitoring not started...", fg="red")
status_label.grid(row=4, column=0, columnspan=2, pady=5)
usb_status_label = tk.Label(root, text="USB Monitoring not started...", fg="red")
usb_status_label.grid(row=5, column=0, columnspan=2, pady=5)

# Log
log_frame = tk.LabelFrame(root, text="Log", padx=10, pady=10)
log_frame.grid(row=6, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
log_text = tk.Text(log_frame, state=tk.DISABLED, width=80, height=10)
log_text.pack()

# Create USB monitor instance
usb_monitor = USBMonitor(
    selected_tasks=[],
    custom_commands=[],
    file_to_delete="",
    process_to_kill=""
)

# Start the Tkinter event loop
root.mainloop()
