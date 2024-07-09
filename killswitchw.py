import tkinter as tk
from tkinter import messagebox, filedialog
import subprocess
import threading
import time
import platform
import os
import sys
import ctypes

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

    def get_current_usb_devices(self):
        devices = []
        if self.os_type == "Windows":
            result = subprocess.run(["wmic", "path", "Win32_USBControllerDevice", "get", "Dependent"], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "Win32_PnPEntity.DeviceID=" in line:
                        devices.append(line.split('=')[1].strip().strip('"'))
        elif self.os_type == "Linux":
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
        if self.os_type == "Windows":
            drives = subprocess.run("wmic logicaldisk get name", capture_output=True, text=True).stdout.split()
            return any(drive.startswith(self.usb_label) for drive in drives)
        elif self.os_type == "Linux":
            return os.path.ismount(f"/media/{self.usb_label}")
        return False

    def dismount_veracrypt_volumes(self):
        subprocess.run("veracrypt /d", shell=True)

    def kill_process(self):
        if self.process_to_kill:
            os.chdir(os.getenv("SystemRoot") or "C:\\Windows")
            result = subprocess.run(f"taskkill /f /im {self.process_to_kill}", shell=True, capture_output=True)
            if result.returncode != 0:
                self.log_message(f"Failed to terminate process: {result.stderr.decode()}")
            else:
                self.log_message("Process terminated successfully.")

    def shutdown_system(self):
        try:
            os.chdir(os.getenv("SystemRoot") or "C:\\Windows")
            subprocess.run("shutdown -s -t 0", shell=True)
        except Exception as e:
            self.log_message(f"Failed to shutdown system: {str(e)}")

    def delete_files(self):
        file_paths = self.file_to_delete.split("; ")
        for file_path in file_paths:
            if file_path:
                try:
                    absolute_file_path = os.path.abspath(file_path)
                    if os.path.isfile(absolute_file_path):
                        quoted_file_path = f'"{absolute_file_path}"'
                        result = subprocess.run(f"del {quoted_file_path}", shell=True, capture_output=True)
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
                        with open(absolute_file_path, 'r+b') as f:
                            length = os.path.getsize(absolute_file_path)
                            f.write(b'\x00' * length)
                        self.log_message("File overwritten successfully.")
                    else:
                        self.log_message(f"File not found: {absolute_file_path}")
                except Exception as e:
                    self.log_message(f"Error overwriting file: {e}")

    def turn_off_screen(self):
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)

    def lock_computer(self):
        ctypes.windll.user32.LockWorkStation()

    def run_custom_commands(self):
        for command in self.custom_commands:
            if command:
                result = subprocess.run(command, shell=True, capture_output=True)
                if result.returncode != 0:
                    self.log_message(f"Failed to execute command: {result.stderr.decode()}")

    def monitor_usb_k_label(self):
        while self.monitoring:
            if not self.k_removed and not self.check_k_label_usb_presence():
                self.log_message("K label USB drive removed.")
                self.k_removed = True
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
                self.run_custom_commands()
                for task in self.selected_tasks:
                    if task == "Shutdown":
                        self.shutdown_system()
            time.sleep(1)

    def on_usb_change(self):
        while self.usb_monitoring:
            if self.check_usb_changes():
                self.log_message("USB device change detected.")
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
                self.run_custom_commands()
                for task in self.selected_tasks:
                    if task == "Shutdown":
                        self.shutdown_system()
            time.sleep(1)

    def start_monitoring(self):
        self.k_removed = False
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_usb_k_label)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def start_usb_monitoring(self):
        self.usb_devices = self.get_current_usb_devices()
        self.usb_monitoring = True
        self.usb_monitor_thread = threading.Thread(target=self.on_usb_change)
        self.usb_monitor_thread.daemon = True
        self.usb_monitor_thread.start()

    def toggle_pause(self):
        self.pause_counter += 1
        if self.pause_counter == 5:
            self.pause_counter = 0
            self.monitoring = False
            start_button.config(state=tk.NORMAL)
            pause_button.config(state=tk.DISABLED)

    def toggle_usb_pause(self):
        self.usb_pause_counter += 1
        if self.usb_pause_counter == 5:
            self.usb_pause_counter = 0
            self.usb_monitoring = False
            usb_start_button.config(state=tk.NORMAL)
            usb_pause_button.config(state=tk.DISABLED)

    def log_message(self, message):
        log_message(message)

def on_start_button_click():
    selected_tasks = [task.get() for task in tasks if task.get()]
    if not selected_tasks:
        messagebox.showerror("Error", "Please select at least one task")
        return
    custom_commands = [command_entry1.get(), command_entry2.get(), command_entry3.get()]
    file_to_delete = file_entry.get()
    process_to_kill = process_entry.get()
    if usb_monitor.monitoring:
        status_label.config(text="Monitoring resumed...")
    else:
        usb_monitor.selected_tasks = selected_tasks
        usb_monitor.custom_commands = custom_commands
        usb_monitor.file_to_delete = file_to_delete
        usb_monitor.process_to_kill = process_to_kill
        usb_monitor.start_monitoring()
        pause_button.config(state=tk.NORMAL)
        start_button.config(state=tk.DISABLED)
        status_label.config(text="Monitoring started...")

def on_pause_button_click():
    usb_monitor.toggle_pause()
    if usb_monitor.monitoring:
        status_label.config(text="Monitoring resumed...")
    else:
        status_label.config(text="Monitoring paused...")

def on_usb_start_button_click():
    selected_tasks = [task.get() for task in tasks if task.get()]
    if not selected_tasks:
        messagebox.showerror("Error", "Please select at least one task")
        return
    custom_commands = [command_entry1.get(), command_entry2.get(), command_entry3.get()]
    file_to_delete = file_entry.get()
    process_to_kill = process_entry.get()
    if usb_monitor.usb_monitoring:
        usb_status_label.config(text="USB Monitoring resumed...")
    else:
        usb_monitor.selected_tasks = selected_tasks
        usb_monitor.custom_commands = custom_commands
        usb_monitor.file_to_delete = file_to_delete
        usb_monitor.process_to_kill = process_to_kill
        usb_monitor.start_usb_monitoring()
        usb_pause_button.config(state=tk.NORMAL)
        usb_start_button.config(state=tk.DISABLED)
        usb_status_label.config(text="USB Monitoring started...")

def on_usb_pause_button_click():
    usb_monitor.toggle_usb_pause()
    if usb_monitor.usb_monitoring:
        usb_status_label.config(text="USB Monitoring resumed...")
    else:
        usb_status_label.config(text="USB Monitoring paused...")

def select_files():
    file_paths = filedialog.askopenfilenames()
    if file_paths:
        file_entry.delete(0, tk.END)
        file_entry.insert(0, "; ".join(file_paths))

def log_message(message):
    log_text.config(state=tk.NORMAL)
    log_text.insert(tk.END, f"{message}\n")
    log_text.see(tk.END)
    log_text.config(state=tk.DISABLED)

def create_gui():
    global start_button, pause_button, status_label
    global usb_start_button, usb_pause_button, usb_status_label
    global tasks, command_entry1, command_entry2, command_entry3, file_entry
    global process_entry, process_entry2, process_entry3, log_text, usb_monitor

    root = tk.Tk()
    root.title("USB Monitor")
    root.geometry("600x750")

    main_frame = tk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    task_frame = tk.Frame(main_frame)
    task_frame.pack(fill=tk.X, padx=10, pady=10)
    tk.Label(task_frame, text="Select Tasks:").pack(anchor='w')

    tasks = []

    task_dismount = tk.StringVar(value="Dismount VeraCrypt Volumes")
    task_dismount_checkbox = tk.Checkbutton(task_frame, text="Dismount VeraCrypt Volumes", variable=task_dismount, onvalue="Dismount VeraCrypt Volumes", offvalue="", padx=10)
    task_dismount_checkbox.pack(side=tk.TOP, anchor='w')
    tasks.append(task_dismount)

    task_end_process = tk.StringVar(value="End Process")
    task_end_process_checkbox = tk.Checkbutton(task_frame, text="End Process", variable=task_end_process, onvalue="End Process", offvalue="", padx=10)
    task_end_process_checkbox.pack(side=tk.TOP, anchor='w')
    tasks.append(task_end_process)

    task_delete_file = tk.StringVar(value="Delete File")
    task_delete_file_checkbox = tk.Checkbutton(task_frame, text="Delete File", variable=task_delete_file, onvalue="Delete File", offvalue="", padx=10)
    task_delete_file_checkbox.pack(side=tk.TOP, anchor='w')
    tasks.append(task_delete_file)

    task_overwrite_file = tk.StringVar(value="Overwrite File")
    task_overwrite_file_checkbox = tk.Checkbutton(task_frame, text="Overwrite File", variable=task_overwrite_file, onvalue="Overwrite File", offvalue="", padx=10)
    task_overwrite_file_checkbox.pack(side=tk.TOP, anchor='w')
    tasks.append(task_overwrite_file)

    task_turn_off_screen = tk.StringVar(value="Turn Off Screen")
    task_turn_off_screen_checkbox = tk.Checkbutton(task_frame, text="Turn Off Screen", variable=task_turn_off_screen, onvalue="Turn Off Screen", offvalue="", padx=10)
    task_turn_off_screen_checkbox.pack(side=tk.TOP, anchor='w')
    tasks.append(task_turn_off_screen)

    task_lock_computer = tk.StringVar(value="Lock Computer")
    task_lock_computer_checkbox = tk.Checkbutton(task_frame, text="Lock Computer", variable=task_lock_computer, onvalue="Lock Computer", offvalue="", padx=10)
    task_lock_computer_checkbox.pack(side=tk.TOP, anchor='w')
    tasks.append(task_lock_computer)

    task_shutdown = tk.StringVar(value="Shutdown")
    task_shutdown_checkbox = tk.Checkbutton(task_frame, text="Shutdown", variable=task_shutdown, onvalue="Shutdown", offvalue="", padx=10)
    task_shutdown_checkbox.pack(side=tk.TOP, anchor='w')
    tasks.append(task_shutdown)

    # Command entries
    command_label1 = tk.Label(main_frame, text="Custom Command 1:")
    command_label1.pack(anchor='w', padx=10)
    command_entry1 = tk.Entry(main_frame)
    command_entry1.pack(fill=tk.X, padx=10, pady=5)

    command_label2 = tk.Label(main_frame, text="Custom Command 2:")
    command_label2.pack(anchor='w', padx=10)
    command_entry2 = tk.Entry(main_frame)
    command_entry2.pack(fill=tk.X, padx=10, pady=5)

    command_label3 = tk.Label(main_frame, text="Custom Command 3:")
    command_label3.pack(anchor='w', padx=10)
    command_entry3 = tk.Entry(main_frame)
    command_entry3.pack(fill=tk.X, padx=10, pady=5)

    # File entry for deletion with file selector
    file_label = tk.Label(main_frame, text="File to Delete/Overwrite:")
    file_label.pack(anchor='w', padx=10)
    file_frame = tk.Frame(main_frame)
    file_frame.pack(fill=tk.X, padx=10, pady=5)
    file_entry = tk.Entry(file_frame)
    file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    file_button = tk.Button(file_frame, text="Select Files", command=select_files)
    file_button.pack(side=tk.LEFT)

    # Process selection entry fields
    process_label = tk.Label(main_frame, text="Enter Process to Kill:")
    process_label.pack(anchor='w', padx=10)
    process_entry = tk.Entry(main_frame)
    process_entry.pack(fill=tk.X, padx=10, pady=5)

    process_label2 = tk.Label(main_frame, text="Enter Process to Kill:")
    process_label2.pack(anchor='w', padx=10)
    process_entry2 = tk.Entry(main_frame)
    process_entry2.pack(fill=tk.X, padx=10, pady=5)

    process_label3 = tk.Label(main_frame, text="Enter Process to Kill:")
    process_label3.pack(anchor='w', padx=10)
    process_entry3 = tk.Entry(main_frame)
    process_entry3.pack(fill=tk.X, padx=10, pady=5)

    # Buttons
    button_frame = tk.Frame(main_frame)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    start_button = tk.Button(button_frame, text="Arm", command=on_start_button_click)
    start_button.pack(side=tk.LEFT, padx=5)

    pause_button = tk.Button(button_frame, text="Disarm (press 5 times)", command=on_pause_button_click, state=tk.DISABLED)
    pause_button.pack(side=tk.LEFT, padx=5)

    status_label = tk.Label(main_frame, text="")
    status_label.pack(fill=tk.X, padx=10, pady=5)

    usb_start_button = tk.Button(button_frame, text="Arm USB Monitoring", command=on_usb_start_button_click)
    usb_start_button.pack(side=tk.LEFT, padx=5)

    usb_pause_button = tk.Button(button_frame, text="Disarm USB Monitoring (press 5 times)", command=on_usb_pause_button_click, state=tk.DISABLED)
    usb_pause_button.pack(side=tk.LEFT, padx=5)

    usb_status_label = tk.Label(main_frame, text="")
    usb_status_label.pack(fill=tk.X, padx=10, pady=5)

    # Log display
    log_frame = tk.Frame(main_frame)
    log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    log_text = tk.Text(log_frame, wrap=tk.WORD, height=10, state=tk.DISABLED)
    log_text.pack(fill=tk.BOTH, expand=True)

    usb_monitor = USBMonitor([], [], "", "")

    root.mainloop()

def launch_gui_with_elevated_privileges():
    if ctypes.windll.shell32.IsUserAnAdmin():
        create_gui()
    else:
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch GUI with elevated privileges: {str(e)}")

if __name__ == '__main__':
    launch_gui_with_elevated_privileges()

