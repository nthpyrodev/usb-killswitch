import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import subprocess
import threading
import time
import platform
import os
import sys
import ctypes

class USBMonitor:
    def __init__(self, selected_tasks, custom_commands, file_to_delete, processes_to_kill):
        self.usb_label = "K"  # Default K label set here
        self.selected_tasks = selected_tasks
        self.custom_commands = custom_commands
        self.file_to_delete = file_to_delete
        self.processes_to_kill = processes_to_kill
        self.monitoring = False
        self.usb_monitoring = False
        self.os_type = platform.system()
        self.usb_devices = self.get_current_usb_devices()
        self.pause_counter = 0
        self.usb_pause_counter = 0
        self.drive_removed = False
        self.veracrypt_timeout = 30

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
            return os.path.ismount(f"/media/{self.usb_label}") # Assumes that the usb is in /media
        return False

    def dismount_veracrypt_volumes(self):
        try:
            self.log_message("Attempting to dismount VeraCrypt volumes...")
            dismount_thread = threading.Thread(target=self._dismount_veracrypt_task)
            dismount_thread.daemon = True
            dismount_thread.start()
            
            dismount_thread.join(timeout=self.veracrypt_timeout)
            
            if dismount_thread.is_alive():
                self.log_message(f"VeraCrypt dismount taking too long (>{self.veracrypt_timeout}s). Proceeding with next actions.")
                return False
            return True
        except Exception as e:
            self.log_message(f"Error during VeraCrypt dismount: {str(e)}")
            return False

    def _dismount_veracrypt_task(self):
        subprocess.run("veracrypt /d", shell=True)
        self.log_message("VeraCrypt volumes dismounted successfully.")

    def kill_process(self):
        if self.processes_to_kill:
            os.chdir(os.getenv("SystemRoot") or "C:\\Windows")
            for process in self.processes_to_kill:
                if process.strip():
                    result = subprocess.run(f"taskkill /f /im {process}", shell=True, capture_output=True)
                    if result.returncode != 0:
                        self.log_message(f"Failed to terminate process: {result.stderr.decode()}")
                    else:
                        self.log_message(f"Process {process} terminated successfully.")

    def shutdown_system(self):
        try:
            self.log_message("Initiating system shutdown...")
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
                            self.log_message(f"File deleted successfully: {absolute_file_path}")
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
                        self.log_message(f"File overwritten successfully: {absolute_file_path}")
                    else:
                        self.log_message(f"File not found: {absolute_file_path}")
                except Exception as e:
                    self.log_message(f"Error overwriting file: {e}")

    def turn_off_screen(self):
        self.log_message("Turning off screen...")
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)

    def lock_computer(self):
        self.log_message("Locking computer...")
        ctypes.windll.user32.LockWorkStation()

    def run_custom_commands(self):
        for command in self.custom_commands:
            if command:
                self.log_message(f"Executing command: {command}")
                result = subprocess.run(command, shell=True, capture_output=True)
                if result.returncode != 0:
                    self.log_message(f"Failed to execute command: {result.stderr.decode()}")
                else:
                    self.log_message("Command executed successfully.")

    def monitor_usb_k_label(self):
        while self.monitoring:
            if not self.k_removed and not self.check_k_label_usb_presence():
                self.log_message("K label USB drive removed. Executing tasks...")
                self.k_removed = True
                self.execute_tasks()
            time.sleep(1)

    def on_usb_change(self):
        while self.usb_monitoring:
            if self.check_usb_changes():
                self.log_message("USB device change detected. Executing tasks...")
                self.execute_tasks()
            time.sleep(1)

    def execute_tasks(self):
        shutdown_required = "Shutdown" in self.selected_tasks
        
        for task in self.selected_tasks:
            if task == "Dismount VeraCrypt Volumes":
                self.dismount_veracrypt_volumes()
            elif task == "End Process":
                self.kill_process()
            elif task == "Delete File":
                self.delete_files()
            elif task == "Overwrite File":
                self.overwrite_files()
            elif task == "Turn Off Screen":
                self.turn_off_screen()
            elif task == "Lock Computer":
                self.lock_computer()
        
        self.run_custom_commands()
        
        if shutdown_required:
            self.shutdown_system()

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
    
    custom_commands = []
    for command_entry in command_entries:
        if command_entry.get().strip():
            custom_commands.append(command_entry.get().strip())
    
    processes_to_kill = []
    for process_entry in process_entries:
        if process_entry.get().strip():
            processes_to_kill.append(process_entry.get().strip())
    
    file_to_delete = file_entry.get()
    
    try:
        timeout_value = int(veracrypt_timeout_entry.get())
        if timeout_value > 0:
            usb_monitor.veracrypt_timeout = timeout_value
    except ValueError:
        pass
    
    if usb_monitor.monitoring:
        status_label.config(text="Monitoring started...")
    else:
        usb_monitor.selected_tasks = selected_tasks
        usb_monitor.custom_commands = custom_commands
        usb_monitor.file_to_delete = file_to_delete
        usb_monitor.processes_to_kill = processes_to_kill
        usb_monitor.start_monitoring()
        pause_button.config(state=tk.NORMAL)
        start_button.config(state=tk.DISABLED)
        status_label.config(text="Monitoring started...")
        log_message(f"{usb_monitor.usb_label}-drive monitoring armed and ready.")

def on_pause_button_click():
    usb_monitor.toggle_pause()
    if usb_monitor.monitoring:
        status_label.config(text="Monitoring started...")
    else:
        status_label.config(text="Monitoring paused...")
        if usb_monitor.pause_counter == 0:
            log_message(f"{usb_monitor.usb_label}-drive monitoring disarmed.")

def on_usb_start_button_click():
    selected_tasks = [task.get() for task in tasks if task.get()]
    if not selected_tasks:
        messagebox.showerror("Error", "Please select at least one task")
        return
    
    custom_commands = []
    for command_entry in command_entries:
        if command_entry.get().strip():
            custom_commands.append(command_entry.get().strip())
    
    processes_to_kill = []
    for process_entry in process_entries:
        if process_entry.get().strip():
            processes_to_kill.append(process_entry.get().strip())
    
    file_to_delete = file_entry.get()
    
    try:
        timeout_value = int(veracrypt_timeout_entry.get())
        if timeout_value > 0:
            usb_monitor.veracrypt_timeout = timeout_value
    except ValueError:
        pass
    
    if usb_monitor.usb_monitoring:
        usb_status_label.config(text="USB Monitoring started...")
    else:
        usb_monitor.selected_tasks = selected_tasks
        usb_monitor.custom_commands = custom_commands
        usb_monitor.file_to_delete = file_to_delete
        usb_monitor.processes_to_kill = processes_to_kill
        usb_monitor.start_usb_monitoring()
        usb_pause_button.config(state=tk.NORMAL)
        usb_start_button.config(state=tk.DISABLED)
        usb_status_label.config(text="USB Monitoring started...")
        log_message("USB change monitoring armed and ready.")

def on_usb_pause_button_click():
    usb_monitor.toggle_usb_pause()
    if usb_monitor.usb_monitoring:
        usb_status_label.config(text="USB Monitoring started...")
    else:
        usb_status_label.config(text="USB Monitoring paused...")
        if usb_monitor.usb_pause_counter == 0:
            log_message("USB change monitoring disarmed.")

def select_files():
    file_paths = filedialog.askopenfilenames()
    if file_paths:
        file_entry.delete(0, tk.END)
        file_entry.insert(0, "; ".join(file_paths))

def log_message(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_text.config(state=tk.NORMAL)
    log_text.insert(tk.END, f"[{timestamp}] {message}\n")
    log_text.see(tk.END)
    log_text.config(state=tk.DISABLED)

def add_process_entry():
    process_entry = ttk.Entry(process_entries_frame)
    process_entry.pack(fill=tk.X, padx=5, pady=2)
    process_entries.append(process_entry)

def add_command_entry():
    command_entry = ttk.Entry(command_entries_frame)
    command_entry.pack(fill=tk.X, padx=5, pady=2)
    command_entries.append(command_entry)

def change_usb_label(event=None):
    new_label = usb_label_entry.get().strip()
    if new_label:
        usb_monitor.usb_label = new_label
        log_message(f"USB label changed to: {new_label}")
        start_button.config(text=f"Arm {new_label}-Drive Monitor")

def on_tab_changed(event):
    notebook.focus_set()

def create_gui():
    global start_button, pause_button, status_label
    global usb_start_button, usb_pause_button, usb_status_label
    global tasks, command_entries, file_entry, process_entries
    global log_text, usb_monitor, usb_label_entry, veracrypt_timeout_entry
    global notebook, process_entries_frame, command_entries_frame

    root = tk.Tk()
    root.title("USB Killswitch")
    root.geometry("650x750")
    root.configure(bg="#f0f0f0")
    
    try:
        root.iconbitmap("icon.ico") # if icon is not available, doesn't matter
    except:
        pass

    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TFrame', background='#f0f0f0')
    style.configure('TButton', font=('Arial', 10), background='#4a7abc')
    style.configure('TCheckbutton', font=('Arial', 10), background='#f0f0f0')
    style.configure('TLabel', font=('Arial', 10), background='#f0f0f0')
    style.configure('TNotebook', background='#f0f0f0')
    style.map('TButton', 
        background=[('active', '#5a8adc'), ('disabled', '#cccccc')],
        foreground=[('disabled', '#888888')])

    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    notebook.bind("<<NotebookTabChanged>>", on_tab_changed)

    main_tab = ttk.Frame(notebook, style='TFrame')
    notebook.add(main_tab, text="Configuration")

    monitoring_tab = ttk.Frame(notebook, style='TFrame')
    notebook.add(monitoring_tab, text="Monitoring Controls")

    log_tab = ttk.Frame(notebook, style='TFrame')
    notebook.add(log_tab, text="Logs")
    
    docs_tab = ttk.Frame(notebook, style='TFrame')
    notebook.add(docs_tab, text="Documentation")

    config_frame = ttk.LabelFrame(main_tab, text="Configuration Settings")
    config_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    usb_label_frame = ttk.Frame(config_frame)
    usb_label_frame.pack(fill=tk.X, padx=10, pady=5)
    ttk.Label(usb_label_frame, text="USB Drive Label to Monitor:").pack(side=tk.LEFT)
    usb_label_entry = ttk.Entry(usb_label_frame, width=5)
    usb_label_entry.insert(0, "K")
    usb_label_entry.pack(side=tk.LEFT, padx=5)
    usb_label_entry.bind("<FocusOut>", change_usb_label)
    
    veracrypt_timeout_frame = ttk.Frame(config_frame)
    veracrypt_timeout_frame.pack(fill=tk.X, padx=10, pady=5)
    ttk.Label(veracrypt_timeout_frame, text="VeraCrypt Dismount Timeout (seconds):").pack(side=tk.LEFT)
    veracrypt_timeout_entry = ttk.Entry(veracrypt_timeout_frame, width=5)
    veracrypt_timeout_entry.insert(0, "30")
    veracrypt_timeout_entry.pack(side=tk.LEFT, padx=5)
    
    task_frame = ttk.LabelFrame(config_frame, text="Select Tasks to Execute")
    task_frame.pack(fill=tk.X, padx=10, pady=10)

    tasks = []

    task_grid = ttk.Frame(task_frame)
    task_grid.pack(fill=tk.X, padx=5, pady=5)

    task_dismount = tk.StringVar(value="Dismount VeraCrypt Volumes")
    task_dismount_checkbox = ttk.Checkbutton(task_grid, text="Dismount VeraCrypt Volumes", 
                                             variable=task_dismount, onvalue="Dismount VeraCrypt Volumes", offvalue="")
    task_dismount_checkbox.grid(row=0, column=0, sticky='w', padx=5, pady=2)
    tasks.append(task_dismount)

    task_end_process = tk.StringVar(value="End Process")
    task_end_process_checkbox = ttk.Checkbutton(task_grid, text="End Process", 
                                               variable=task_end_process, onvalue="End Process", offvalue="")
    task_end_process_checkbox.grid(row=0, column=1, sticky='w', padx=5, pady=2)
    tasks.append(task_end_process)

    task_delete_file = tk.StringVar(value="Delete File")
    task_delete_file_checkbox = ttk.Checkbutton(task_grid, text="Delete File", 
                                               variable=task_delete_file, onvalue="Delete File", offvalue="")
    task_delete_file_checkbox.grid(row=1, column=0, sticky='w', padx=5, pady=2)
    tasks.append(task_delete_file)

    task_overwrite_file = tk.StringVar(value="Overwrite File")
    task_overwrite_file_checkbox = ttk.Checkbutton(task_grid, text="Overwrite File", 
                                                  variable=task_overwrite_file, onvalue="Overwrite File", offvalue="")
    task_overwrite_file_checkbox.grid(row=1, column=1, sticky='w', padx=5, pady=2)
    tasks.append(task_overwrite_file)

    task_turn_off_screen = tk.StringVar(value="Turn Off Screen")
    task_turn_off_screen_checkbox = ttk.Checkbutton(task_grid, text="Turn Off Screen", 
                                                   variable=task_turn_off_screen, onvalue="Turn Off Screen", offvalue="")
    task_turn_off_screen_checkbox.grid(row=2, column=0, sticky='w', padx=5, pady=2)
    tasks.append(task_turn_off_screen)

    task_lock_computer = tk.StringVar(value="Lock Computer")
    task_lock_computer_checkbox = ttk.Checkbutton(task_grid, text="Lock Computer", 
                                                 variable=task_lock_computer, onvalue="Lock Computer", offvalue="")
    task_lock_computer_checkbox.grid(row=2, column=1, sticky='w', padx=5, pady=2)
    tasks.append(task_lock_computer)

    task_shutdown = tk.StringVar(value="Shutdown")
    task_shutdown_checkbox = ttk.Checkbutton(task_grid, text="Shutdown", 
                                            variable=task_shutdown, onvalue="Shutdown", offvalue="")
    task_shutdown_checkbox.grid(row=3, column=0, sticky='w', padx=5, pady=2)
    tasks.append(task_shutdown)

    process_frame = ttk.LabelFrame(config_frame, text="Process Management")
    process_frame.pack(fill=tk.X, padx=10, pady=5)
    
    ttk.Label(process_frame, text="Processes to Kill:").pack(anchor='w', padx=5, pady=2)
    
    process_entries_frame = ttk.Frame(process_frame)
    process_entries_frame.pack(fill=tk.X, padx=5, pady=2)
    
    process_entries = []
    initial_process_entry = ttk.Entry(process_entries_frame)
    initial_process_entry.pack(fill=tk.X, padx=5, pady=2)
    process_entries.append(initial_process_entry)
    
    add_process_button = ttk.Button(process_frame, text="Add More Processes", command=add_process_entry)
    add_process_button.pack(anchor='e', padx=5, pady=5)

    file_frame = ttk.LabelFrame(config_frame, text="File Management")
    file_frame.pack(fill=tk.X, padx=10, pady=5)
    
    ttk.Label(file_frame, text="Files to Delete/Overwrite:").pack(anchor='w', padx=5, pady=2)
    file_selection_frame = ttk.Frame(file_frame)
    file_selection_frame.pack(fill=tk.X, padx=5, pady=2)
    file_entry = ttk.Entry(file_selection_frame)
    file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    file_button = ttk.Button(file_selection_frame, text="Select Files", command=select_files)
    file_button.pack(side=tk.LEFT, padx=5)

    command_frame = ttk.LabelFrame(config_frame, text="Custom Commands")
    command_frame.pack(fill=tk.X, padx=10, pady=5)
    
    ttk.Label(command_frame, text="Commands to Execute:").pack(anchor='w', padx=5, pady=2)
    
    command_entries_frame = ttk.Frame(command_frame)
    command_entries_frame.pack(fill=tk.X, padx=5, pady=2)
    
    command_entries = []
    initial_command_entry = ttk.Entry(command_entries_frame)
    initial_command_entry.pack(fill=tk.X, padx=5, pady=2)
    command_entries.append(initial_command_entry)
    
    add_command_button = ttk.Button(command_frame, text="Add More Commands", command=add_command_entry)
    add_command_button.pack(anchor='e', padx=5, pady=5)

    monitor_frame = ttk.Frame(monitoring_tab)
    monitor_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    k_monitor_frame = ttk.LabelFrame(monitor_frame, text="Drive Monitoring")
    k_monitor_frame.pack(fill=tk.X, padx=10, pady=10)
    
    k_button_frame = ttk.Frame(k_monitor_frame)
    k_button_frame.pack(fill=tk.X, padx=5, pady=10)
    
    start_button = ttk.Button(k_button_frame, text="Arm Specified-Drive Monitor", command=on_start_button_click)
    start_button.pack(side=tk.LEFT, padx=5)
    
    pause_button = ttk.Button(k_button_frame, text="Disarm (Press 5 Times)", 
                              command=on_pause_button_click, state=tk.DISABLED)
    pause_button.pack(side=tk.LEFT, padx=5)
    
    status_label = ttk.Label(k_monitor_frame, text="Status: Not Armed")
    status_label.pack(fill=tk.X, padx=5, pady=5)

    usb_monitor_frame = ttk.LabelFrame(monitor_frame, text="USB Change Monitoring")
    usb_monitor_frame.pack(fill=tk.X, padx=10, pady=10)
    
    usb_button_frame = ttk.Frame(usb_monitor_frame)
    usb_button_frame.pack(fill=tk.X, padx=5, pady=10)
    
    usb_start_button = ttk.Button(usb_button_frame, text="Arm USB Change Monitor", 
                                 command=on_usb_start_button_click)
    usb_start_button.pack(side=tk.LEFT, padx=5)
    
    usb_pause_button = ttk.Button(usb_button_frame, text="Disarm (Press 5 Times)", 
                                  command=on_usb_pause_button_click, state=tk.DISABLED)
    usb_pause_button.pack(side=tk.LEFT, padx=5)
    
    usb_status_label = ttk.Label(usb_monitor_frame, text="Status: Not Armed")
    usb_status_label.pack(fill=tk.X, padx=5, pady=5)

    # commented out until I add something to show actual status, like if no tasks are selected, then it shouldn't work
#    status_info_frame = ttk.LabelFrame(monitor_frame, text="Current Status")
#    status_info_frame.pack(fill=tk.X, padx=10, pady=10)
    
#    current_status_text = tk.Text(status_info_frame, height=4, wrap=tk.WORD)
#    current_status_text.pack(fill=tk.X, padx=5, pady=5)
#    current_status_text.insert(tk.END, "System ready. Configure settings in the Configuration tab, then arm the monitors here.")
#    current_status_text.config(state=tk.DISABLED)

    log_frame = ttk.Frame(log_tab)
    log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    log_text_frame = ttk.Frame(log_frame)
    log_text_frame.pack(fill=tk.BOTH, expand=True)
    
    scrollbar = ttk.Scrollbar(log_text_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    log_text = tk.Text(log_text_frame, wrap=tk.WORD, height=30, state=tk.DISABLED, 
                      yscrollcommand=scrollbar.set)
    log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
    scrollbar.config(command=log_text.yview)
    
    clear_log_button = ttk.Button(log_frame, text="Clear Log", 
                                 command=lambda: [log_text.config(state=tk.NORMAL), 
                                                 log_text.delete(1.0, tk.END), 
                                                 log_text.config(state=tk.DISABLED)])
    clear_log_button.pack(side=tk.RIGHT, padx=5, pady=5)
    
    docs_frame = ttk.Frame(docs_tab)
    docs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    docs_text = tk.Text(docs_frame, wrap=tk.WORD, height=30, padx=10, pady=10)
    docs_text.pack(fill=tk.BOTH, expand=True)
    
    docs_content = """USB Killswitch Documentation

Full docs coming soon, but for the moment, here are a few points you may want to know:
- Specified Drive Monitoring will only monitor if the drive with the specified label is pulled out
- USB Change Monitor will check for any USB device changes
- If the veracrypt volumes take more time to dismount than specified, then other actions will proceed regardless
- Linux is not supported, so only use this tool with Windows for the time being

This project is still in development, so please feel free to contribute to the repo (https://github.com/nthpyrodev/usb-killswitch), report bugs, or donate.

"""
    docs_text.insert(tk.END, docs_content)
    docs_text.config(state=tk.DISABLED)

    usb_monitor = USBMonitor([], [], "", [])
    log_message("USB Killswitch Monitor started. Configure and arm to begin monitoring.")

    notebook.focus_set()

    root.mainloop()

def on_tab_changed(event):
    notebook.focus_set()

def select_files():
    file_paths = filedialog.askopenfilenames()
    if file_paths:
        file_entry.delete(0, tk.END)
        file_entry.insert(0, "; ".join(file_paths))

def log_message(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_text.config(state=tk.NORMAL)
    log_text.insert(tk.END, f"[{timestamp}] {message}\n")
    log_text.see(tk.END)
    log_text.config(state=tk.DISABLED)

def on_pause_button_click():
    usb_monitor.toggle_pause()
    if usb_monitor.monitoring:
        status_label.config(text="Monitoring started...")
    else:
        status_label.config(text="Monitoring paused...")
        if usb_monitor.pause_counter == 0:
            log_message(f"{usb_monitor.usb_label}-drive monitoring disarmed.")

def on_usb_pause_button_click():
    usb_monitor.toggle_usb_pause()
    if usb_monitor.usb_monitoring:
        usb_status_label.config(text="USB Monitoring started...")
    else:
        usb_status_label.config(text="USB Monitoring paused...")
        if usb_monitor.usb_pause_counter == 0:
            log_message("USB change monitoring disarmed.")

def launch_gui_with_elevated_privileges():
    if platform.system() == "Windows":
        try:
            if ctypes.windll.shell32.IsUserAnAdmin():
                create_gui()
            else:
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch GUI with elevated privileges: {str(e)}")
    else:
        create_gui()

if __name__ == '__main__':
    launch_gui_with_elevated_privileges()
