import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import subprocess
import threading
import time
import platform
import os
import sys

usbIdentifier = "K"
selectedTasks = []
customCommands = []
fileToDelete = ""
processesToKill = []
monitoring = False
usbMonitoring = False
osType = "Linux"
usbDevices = []
pauseCounter = 0
usbPauseCounter = 0
driveRemoved = False
usbTimeout = 15
veracryptTimeout = 30
shutdownMode = "immediate"
volumesToDismount = []
shredPasses = 10
identifierRemoved = False
systemVolumesCache = []
nonSystemVolumesCache = []
lastCacheUpdate = 0

def getCurrentUsbDevices():
    devices = []
    try:
        result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            devices = result.stdout.splitlines()
        
        result = subprocess.run(["mount"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if any(pattern in line for pattern in ["/dev/sd", "/dev/usb", "/media", "/mnt"]):
                    devices.append(line)
    except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        logMessage(f"Error getting USB devices: {str(e)}")
    return devices

def checkUsbChanges():
    global usbDevices
    try:
        currentDevices = getCurrentUsbDevices()
        if set(currentDevices) != set(usbDevices):
            usbDevices = currentDevices
            return True
        return False
    except Exception as e:
        logMessage(f"Error checking USB changes: {str(e)}")
        return False

def checkIdentifierUsbPresence():
    try:
        possiblePaths = [
            f"/media/{os.getenv('USER')}/{usbIdentifier}",
            f"/media/{usbIdentifier}",
            f"/mnt/{usbIdentifier}",
            f"/run/media/{os.getenv('USER')}/{usbIdentifier}"
        ]
        return any(os.path.ismount(path) for path in possiblePaths)
    except Exception as e:
        logMessage(f"Error checking USB identifier presence: {str(e)}")
        return False

def getMountedUsbVolumes():
    mountedVolumes = []
    try:
        result = subprocess.run(["mount"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if any(pattern in line for pattern in ["/dev/sd", "/dev/usb", "/media", "/run/media"]):
                    parts = line.split(" ")
                    if len(parts) >= 3:
                        device = parts[0]
                        mountPoint = parts[2]
                        mountedVolumes.append((device, mountPoint))
    except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        logMessage(f"Error getting mounted USB volumes: {str(e)}")
    return mountedVolumes

def isSystemVolume(device, mountPoint):
    global systemVolumesCache, nonSystemVolumesCache, lastCacheUpdate
    
    cacheAge = time.time() - lastCacheUpdate
    if cacheAge < 60:  # Cache valid for 60 seconds, I should reconsider this
        if device in systemVolumesCache or mountPoint in systemVolumesCache:
            return True
        if device in nonSystemVolumesCache and mountPoint in nonSystemVolumesCache:
            return False
    
    criticalMounts = ['/', '/boot', '/home', '/var', '/usr', '/etc', '/bin', '/sbin']
    if mountPoint in criticalMounts:
        systemVolumesCache.append(device)
        systemVolumesCache.append(mountPoint)
        lastCacheUpdate = time.time()
        return True
    
    # Check if it's listed in fstab (permanent mounts)
    try:
        fstabResult = subprocess.run(["grep", device, "/etc/fstab"], 
                                     capture_output=True, text=True, timeout=5)
        if fstabResult.returncode == 0 and fstabResult.stdout.strip():
            systemVolumesCache.append(device)
            systemVolumesCache.append(mountPoint)
            lastCacheUpdate = time.time()
            return True
    except:
        pass
    
    try:
        if any(fs in mountPoint for fs in ['nfs', 'cifs', 'smb']):
            systemVolumesCache.append(device)
            systemVolumesCache.append(mountPoint)
            lastCacheUpdate = time.time()
            return True
            
        if ('/media/' in mountPoint or '/run/media/' in mountPoint) and '/dev/sd' in device:
            nonSystemVolumesCache.append(device)
            nonSystemVolumesCache.append(mountPoint)
            lastCacheUpdate = time.time()
            return False
    except:
        pass
    
    # If uncertain, assume it's a system volume. Maybe I should take the opposite approach.
    systemVolumesCache.append(device)
    systemVolumesCache.append(mountPoint)
    lastCacheUpdate = time.time()
    return True

def updateVolumeCache():
    global systemVolumesCache, nonSystemVolumesCache, lastCacheUpdate
    
    try:
        systemVolumesCache = []
        nonSystemVolumesCache = []
        
        mountedVolumes = getMountedUsbVolumes()
        for device, mountPoint in mountedVolumes:
            isSystemVolume(device, mountPoint)
            
        lastCacheUpdate = time.time()
        logMessage("Volume cache updated")
    except Exception as e:
        logMessage(f"Error updating volume cache: {str(e)}")

def dismountUsbVolumes():
    try:
        logMessage("Attempting to dismount USB volumes...")
        dismountThread = threading.Thread(target=dismountUsbVolumesTask)
        dismountThread.daemon = True
        dismountThread.start()
        
        dismountThread.join(timeout=usbTimeout)
        
        if dismountThread.is_alive():
            logMessage(f"USB volume dismounting taking too long (>{usbTimeout}s). Proceeding with next actions.")
            return False
        return True
    except Exception as e:
        logMessage(f"Error during USB volume dismount: {str(e)}")
        return False

def dismountUsbVolumesTask():
    try:
        mountedVolumes = getMountedUsbVolumes()
        
        if volumesToDismount:
            for device, mountPoint in mountedVolumes:
                if device in volumesToDismount or mountPoint in volumesToDismount:
                    dismountVolume(device, mountPoint)
        else:
            for device, mountPoint in mountedVolumes:
                if not isSystemVolume(device, mountPoint):
                    dismountVolume(device, mountPoint)
    except Exception as e:
        logMessage(f"Error in dismount task: {str(e)}")

def dismountVolume(device, mountPoint):
    try:
        logMessage(f"Dismounting {device} from {mountPoint}...")
        result = subprocess.run(["umount", mountPoint], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            logMessage(f"Standard unmount failed, trying lazy unmount for {mountPoint}")
            result = subprocess.run(["umount", "-l", mountPoint], capture_output=True, text=True, timeout=5)
            
        if result.returncode == 0:
            logMessage(f"Successfully dismounted {mountPoint}")
        else:
            logMessage(f"Failed to dismount {mountPoint}: {result.stderr}")
    except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        logMessage(f"Error dismounting {mountPoint}: {str(e)}")

def dismountVeracryptVolumes():
    try:
        logMessage("Attempting to dismount VeraCrypt volumes...")
        dismountThread = threading.Thread(target=dismountVeracryptTask)
        dismountThread.daemon = True
        dismountThread.start()
        
        dismountThread.join(timeout=veracryptTimeout)
        
        if dismountThread.is_alive():
            logMessage(f"VeraCrypt dismount taking too long (>{veracryptTimeout}s). Proceeding with next actions.")
            return False
        return True
    except Exception as e:
        logMessage(f"Error during VeraCrypt dismount: {str(e)}")
        return False

def dismountVeracryptTask():
    try:
        subprocess.run("veracrypt -d", shell=True, timeout=veracryptTimeout-2)
        logMessage("VeraCrypt volumes dismounted successfully.")
    except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        logMessage(f"Error in VeraCrypt dismount task: {str(e)}")

def killProcess():
    if not processesToKill:
        return
        
    for process in processesToKill:
        if not process.strip():
            continue
            
        try:
            logMessage(f"Attempting to terminate process: {process}")
            result = subprocess.run(f"pkill -9 {process}", shell=True, capture_output=True, timeout=5)
            if result.returncode != 0:
                logMessage(f"Failed to terminate process: {result.stderr.decode()}")
            else:
                logMessage(f"Process {process} terminated successfully.")
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            logMessage(f"Error terminating process {process}: {str(e)}")

def shutdownSystem():
    try:
        logMessage("Shutdown will run last after all other processes are complete.")
        logMessage(f"Initiating system {shutdownMode} shutdown...")
        
        if shutdownMode == "forced":
            subprocess.run("sudo poweroff -f", shell=True, timeout=10)
        else:
            subprocess.run("sudo shutdown -h now", shell=True, timeout=10)
            
    except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        logMessage(f"Failed to shutdown system: {str(e)}")

def deleteFiles():
    filePaths = fileToDelete.split("; ")
    for filePath in filePaths:
        if not filePath:
            continue
            
        try:
            absoluteFilePath = os.path.abspath(filePath)
            if os.path.isfile(absoluteFilePath):
                quotedFilePath = f'"{absoluteFilePath}"'
                logMessage(f"Deleting file: {absoluteFilePath}")
                result = subprocess.run(f"rm {quotedFilePath}", shell=True, capture_output=True, timeout=10)
                if result.returncode != 0:
                    logMessage(f"Failed to delete file: {result.stderr.decode()}")
                else:
                    logMessage(f"File deleted successfully: {absoluteFilePath}")
            else:
                logMessage(f"File not found: {absoluteFilePath}")
        except Exception as e:
            logMessage(f"Error deleting file {filePath}: {str(e)}")

def overwriteFiles():
    filePaths = fileToDelete.split("; ")
    for filePath in filePaths:
        if not filePath:
            continue
        
        try:
            absoluteFilePath = os.path.abspath(filePath)
            if os.path.isfile(absoluteFilePath):
                quotedFilePath = f'"{absoluteFilePath}"'
            
                try:
                    fileSizeBytes = os.path.getsize(absoluteFilePath)
                    fileSizeMb = fileSizeBytes / (1024 * 1024)
                    estimatedTime = int(fileSizeMb * shredPasses)
                    timeout = max(30, min(estimatedTime, 3600))
                except:
                    timeout = max(30, shredPasses * 2)
            
                logMessage(f"Shredding file with {shredPasses} passes: {absoluteFilePath} (timeout: {timeout}s)")
            
                shredThread = threading.Thread(
                    target=lambda: subprocess.run(
                        f"shred -zun {shredPasses} {quotedFilePath}", 
                        shell=True, capture_output=True
                    )
                )
                shredThread.daemon = True
                shredThread.start()
            
                shredThread.join(timeout=timeout)
            
                if shredThread.is_alive():
                    logMessage(f"Shredding file {absoluteFilePath} is taking longer than {timeout}s. Continuing with other tasks.")
                else:
                    logMessage(f"File securely shredded: {absoluteFilePath}")
            else:
                logMessage(f"File not found: {absoluteFilePath}")
        except Exception as e:
            logMessage(f"Error overwriting file {filePath}: {str(e)}")

def turnOffScreen():
    logMessage("Turning off screen...")
    methods = [
        "xset dpms force off",
        "vbetool dpms off",
        "xrandr --output $(xrandr | grep ' connected' | head -n 1 | cut -d ' ' -f1) --off"
    ]
    
    for method in methods:
        try:
            subprocess.run(method, shell=True, timeout=5)
            logMessage(f"Screen turned off using: {method}")
            return
        except:
            continue
            
    logMessage("Failed to turn off screen after trying all methods")

def lockComputer():
    logMessage("Locking computer...")
    desktopEnv = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    
    lockCommands = {
        'gnome': ["gnome-screensaver-command -l", "dbus-send --type=method_call --dest=org.gnome.ScreenSaver /org/gnome/ScreenSaver org.gnome.ScreenSaver.Lock"],
        'kde': ["loginctl lock-session"],
        'xfce': ["xflock4"],
        'cinnamon': ["cinnamon-screensaver-command -l"],
        'mate': ["mate-screensaver-command -l"],
        'lxde': ["lxlock"],
        'i3': ["i3lock"],
        'sway': ["swaylock"],
        'unity': ["gnome-screensaver-command -l"]
    }
    
    if desktopEnv in lockCommands:
        for cmd in lockCommands[desktopEnv]:
            try:
                subprocess.run(cmd, shell=True, timeout=5)
                logMessage(f"Screen locked using: {cmd}")
                return
            except:
                continue
    
    genericCommands = [
        "xdg-screensaver lock",
        "loginctl lock-session",
        "light-locker-command -l"
    ]
    
    for cmd in genericCommands:
        try:
            subprocess.run(cmd, shell=True, timeout=5)
            logMessage(f"Screen locked using generic method: {cmd}")
            return
        except:
            continue
            
    logMessage("Failed to lock screen after trying all methods")

def runCustomCommands():
    for command in customCommands:
        if not command:
            continue
            
        try:
            logMessage(f"Executing command: {command}")
            cmdThread = threading.Thread(
                target=lambda: subprocess.run(
                    command, shell=True, capture_output=True
                )
            )
            cmdThread.daemon = True
            cmdThread.start()
            
            cmdThread.join(timeout=30)
            
            if cmdThread.is_alive():
                logMessage(f"Command is taking too long: {command}. Continuing with other tasks.")
            else:
                logMessage(f"Command executed: {command}")
        except Exception as e:
            logMessage(f"Error executing command '{command}': {str(e)}")

def monitorUsbIdentifier():
    global monitoring, identifierRemoved
    
    while monitoring:
        try:
            if not identifierRemoved and not checkIdentifierUsbPresence():
                logMessage(f"{usbIdentifier} identifier USB drive removed. Executing tasks...")
                identifierRemoved = True
                executeTasks()
        except Exception as e:
            logMessage(f"Error in USB identifier monitoring: {str(e)}")
        time.sleep(1)

def onUsbChange():
    global usbMonitoring
    
    while usbMonitoring:
        try:
            if checkUsbChanges():
                logMessage("USB device change detected. Executing tasks...")
                executeTasks()
        except Exception as e:
            logMessage(f"Error in USB change monitoring: {str(e)}")
        time.sleep(1)

def executeTasks():
    global monitoring, usbMonitoring
    
    shutdownRequired = "Shutdown" in selectedTasks
    
    for task in selectedTasks:
        if not monitoring and not usbMonitoring:
            logMessage("Monitoring stopped. Aborting remaining tasks.")
            return
            
        try:
            if task == "Dismount VeraCrypt Volumes":
                dismountVeracryptVolumes()
            elif task == "Dismount USB Volumes":
                dismountUsbVolumes()
            elif task == "End Process":
                killProcess()
            elif task == "Delete File":
                deleteFiles()
            elif task == "Overwrite File":
                overwriteFiles()
            elif task == "Turn Off Screen":
                turnOffScreen()
            elif task == "Lock Computer":
                lockComputer()
        except Exception as e:
            logMessage(f"Error executing task '{task}': {str(e)}")
    
    try:
        runCustomCommands()
    except Exception as e:
        logMessage(f"Error running custom commands: {str(e)}")
    
    if shutdownRequired:
        shutdownSystem()

def startMonitoring():
    global monitoring, identifierRemoved, monitorThread
    
    identifierRemoved = False
    monitoring = True
    monitorThread = threading.Thread(target=monitorUsbIdentifier)
    monitorThread.daemon = True
    monitorThread.start()

def startUsbMonitoring():
    global usbMonitoring, usbDevices, usbMonitorThread
    
    usbDevices = getCurrentUsbDevices()
    usbMonitoring = True
    usbMonitorThread = threading.Thread(target=onUsbChange)
    usbMonitorThread.daemon = True
    usbMonitorThread.start()
    
    updateVolumeCache()

def togglePause():
    global pauseCounter, monitoring
    
    pauseCounter += 1
    if pauseCounter == 5:
        pauseCounter = 0
        monitoring = False
        startButton.config(state=tk.NORMAL)
        pauseButton.config(state=tk.DISABLED)

def toggleUsbPause():
    global usbPauseCounter, usbMonitoring
    
    usbPauseCounter += 1
    if usbPauseCounter == 5:
        usbPauseCounter = 0
        usbMonitoring = False
        usbStartButton.config(state=tk.NORMAL)
        usbPauseButton.config(state=tk.DISABLED)

def onStartButtonClick():
    global selectedTasks, customCommands, fileToDelete, processesToKill
    global veracryptTimeout, usbTimeout, shredPasses, shutdownMode, volumesToDismount
    
    selectedTasks = [task.get() for task in tasks if task.get()]
    if not selectedTasks:
        messagebox.showerror("Error", "Please select at least one task")
        return
    
    customCommands = []
    for commandEntry in commandEntries:
        if commandEntry.get().strip():
            customCommands.append(commandEntry.get().strip())
    
    processesToKill = []
    for processEntry in processEntries:
        if processEntry.get().strip():
            processesToKill.append(processEntry.get().strip())
    
    fileToDelete = fileEntry.get()
    
    try:
        veracryptTimeoutValue = int(veracryptTimeoutEntry.get())
        if veracryptTimeoutValue > 0:
            veracryptTimeout = veracryptTimeoutValue
    except ValueError:
        pass
    
    try:
        usbTimeoutValue = int(usbTimeoutEntry.get())
        if usbTimeoutValue > 0:
            usbTimeout = usbTimeoutValue
    except ValueError:
        pass
    
    try:
        shredPassesValue = int(shredPassesEntry.get())
        if shredPassesValue > 0:
            shredPasses = shredPassesValue
    except ValueError:
        pass
    
    shutdownMode = shutdownModeVar.get()
    
    volumesToDismount = volumesEntry.get().split(";")
    volumesToDismount = [vol.strip() for vol in volumesToDismount if vol.strip()]
    
    if monitoring:
        statusLabel.config(text="Monitoring started...")
    else:
        startMonitoring()
        pauseButton.config(state=tk.NORMAL)
        startButton.config(state=tk.DISABLED)
        statusLabel.config(text="Monitoring started...")
        logMessage(f"{usbIdentifier} identifier monitoring armed and ready.")

def onPauseButtonClick():
    togglePause()
    if monitoring:
        statusLabel.config(text="Monitoring started...")
    else:
        statusLabel.config(text="Monitoring paused...")
        if pauseCounter == 0:
            logMessage(f"{usbIdentifier} identifier monitoring disarmed.")

def onUsbStartButtonClick():
    global selectedTasks, customCommands, fileToDelete, processesToKill
    global veracryptTimeout, usbTimeout, shredPasses, shutdownMode, volumesToDismount
    
    selectedTasks = [task.get() for task in tasks if task.get()]
    if not selectedTasks:
        messagebox.showerror("Error", "Please select at least one task")
        return
    
    customCommands = []
    for commandEntry in commandEntries:
        if commandEntry.get().strip():
            customCommands.append(commandEntry.get().strip())
    
    processesToKill = []
    for processEntry in processEntries:
        if processEntry.get().strip():
            processesToKill.append(processEntry.get().strip())
    
    fileToDelete = fileEntry.get()
    
    try:
        veracryptTimeoutValue = int(veracryptTimeoutEntry.get())
        if veracryptTimeoutValue > 0:
            veracryptTimeout = veracryptTimeoutValue
    except ValueError:
        pass
    
    try:
        usbTimeoutValue = int(usbTimeoutEntry.get())
        if usbTimeoutValue > 0:
            usbTimeout = usbTimeoutValue
    except ValueError:
        pass
    
    try:
        shredPassesValue = int(shredPassesEntry.get())
        if shredPassesValue > 0:
            shredPasses = shredPassesValue
    except ValueError:
        pass
    
    shutdownMode = shutdownModeVar.get()
    
    volumesToDismount = volumesEntry.get().split(";")
    volumesToDismount = [vol.strip() for vol in volumesToDismount if vol.strip()]
    
    if usbMonitoring:
        usbStatusLabel.config(text="USB Monitoring started...")
    else:
        startUsbMonitoring()
        usbPauseButton.config(state=tk.NORMAL)
        usbStartButton.config(state=tk.DISABLED)
        usbStatusLabel.config(text="USB Monitoring started...")
        logMessage("USB change monitoring armed and ready.")

def onUsbPauseButtonClick():
    toggleUsbPause()
    if usbMonitoring:
        usbStatusLabel.config(text="USB Monitoring started...")
    else:
        usbStatusLabel.config(text="USB Monitoring paused...")
        if usbPauseCounter == 0:
            logMessage("USB change monitoring disarmed.")

def selectFiles():
    try:
        filePaths = filedialog.askopenfilenames()
        if filePaths:
            fileEntry.delete(0, tk.END)
            fileEntry.insert(0, "; ".join(filePaths))
    except Exception as e:
        messagebox.showerror("Error", f"Failed to select files: {str(e)}")

def selectVolumes():
    try:
        mountedVolumes = getMountedUsbVolumes()
        
        if not mountedVolumes:
            messagebox.showinfo("No Volumes", "No USB volumes currently mounted")
            return
        
        volumeSelect = tk.Toplevel()
        volumeSelect.title("Select USB Volumes")
        volumeSelect.geometry("500x400")
        
        ttk.Label(volumeSelect, text="Select volumes to dismount:").pack(pady=10)
        
        volumeFrame = ttk.Frame(volumeSelect)
        volumeFrame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        volumeVars = []
        for device, mountPoint in mountedVolumes:
            if not isSystemVolume(device, mountPoint):
                var = tk.BooleanVar(value=False)
                volumeVars.append((var, device, mountPoint))
                cb = ttk.Checkbutton(volumeFrame, 
                                    text=f"{device} mounted at {mountPoint}", 
                                    variable=var)
                cb.pack(anchor='w', padx=5, pady=2)
        
        def onSelect():
            selected = []
            for var, device, mountPoint in volumeVars:
                if var.get():
                    selected.append(device)
            
            volumesEntry.delete(0, tk.END)
            volumesEntry.insert(0, "; ".join(selected))
            volumeSelect.destroy()
        
        def selectAll():
            for var, _, _ in volumeVars:
                var.set(True)
        
        def deselectAll():
            for var, _, _ in volumeVars:
                var.set(False)
        
        buttonFrame = ttk.Frame(volumeSelect)
        buttonFrame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(buttonFrame, text="Select All", command=selectAll).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttonFrame, text="Deselect All", command=deselectAll).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttonFrame, text="OK", command=onSelect).pack(side=tk.RIGHT, padx=5)
        ttk.Button(buttonFrame, text="Cancel", command=volumeSelect.destroy).pack(side=tk.RIGHT, padx=5)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to show volume selection: {str(e)}")

def logMessage(message):
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        logText.config(state=tk.NORMAL)
        logText.insert(tk.END, f"[{timestamp}] {message}\n")
        logText.see(tk.END)
        logText.config(state=tk.DISABLED)
    except Exception as e:
        print(f"Error logging message: {str(e)}")

def addProcessEntry():
    try:
        processEntry = ttk.Entry(processEntriesFrame)
        processEntry.pack(fill=tk.X, padx=5, pady=2)
        processEntries.append(processEntry)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to add process entry: {str(e)}")

def addCommandEntry():
    try:
        commandEntry = ttk.Entry(commandEntriesFrame)
        commandEntry.pack(fill=tk.X, padx=5, pady=2)
        commandEntries.append(commandEntry)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to add command entry: {str(e)}")

def changeUsbIdentifier(event=None):
    global usbIdentifier
    
    try:
        newIdentifier = usbIdentifierEntry.get().strip()
        if newIdentifier:
            usbIdentifier = newIdentifier
            logMessage(f"USB identifier changed to: {newIdentifier}")
            startButton.config(text=f"Arm {newIdentifier}-Identifier Monitor")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to change USB identifier: {str(e)}")

def onTabChanged(event):
    notebook.focus_set()

def createGui():
    global startButton, pauseButton, statusLabel
    global usbStartButton, usbPauseButton, usbStatusLabel
    global tasks, commandEntries, fileEntry, processEntries
    global logText, usbIdentifierEntry, veracryptTimeoutEntry, usbTimeoutEntry
    global notebook, processEntriesFrame, commandEntriesFrame
    global shutdownModeVar, volumesEntry, shredPassesEntry

    try:
        root = tk.Tk()
        root.title("USB Killswitch")
        root.geometry("650x750")
        root.configure(bg="#f0f0f0")

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
        notebook.bind("<<NotebookTabChanged>>", onTabChanged)

        mainTab = ttk.Frame(notebook, style='TFrame')
        notebook.add(mainTab, text="Configuration")

        monitoringTab = ttk.Frame(notebook, style='TFrame')
        notebook.add(monitoringTab, text="Monitoring Controls")

        logTab = ttk.Frame(notebook, style='TFrame')
        notebook.add(logTab, text="Logs")
        
        docsTab = ttk.Frame(notebook, style='TFrame')
        notebook.add(docsTab, text="Documentation")

        configFrame = ttk.LabelFrame(mainTab, text="Configuration Settings")
        configFrame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        usbIdentifierFrame = ttk.Frame(configFrame)
        usbIdentifierFrame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(usbIdentifierFrame, text="USB Identifier to Monitor:").pack(side=tk.LEFT)
        usbIdentifierEntry = ttk.Entry(usbIdentifierFrame, width=10)
        usbIdentifierEntry.insert(0, "K")
        usbIdentifierEntry.pack(side=tk.LEFT, padx=5)
        usbIdentifierEntry.bind("<FocusOut>", changeUsbIdentifier)
        
        timeoutFrame = ttk.Frame(configFrame)
        timeoutFrame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(timeoutFrame, text="VeraCrypt Timeout (sec):").pack(side=tk.LEFT)
        veracryptTimeoutEntry = ttk.Entry(timeoutFrame, width=5)
        veracryptTimeoutEntry.insert(0, "30")
        veracryptTimeoutEntry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(timeoutFrame, text="USB Dismount Timeout (sec):").pack(side=tk.LEFT, padx=(10,0))
        usbTimeoutEntry = ttk.Entry(timeoutFrame, width=5)
        usbTimeoutEntry.insert(0, "15")
        usbTimeoutEntry.pack(side=tk.LEFT, padx=5)
        
        shredFrame = ttk.Frame(configFrame)
        shredFrame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(shredFrame, text="Shred Overwrites:").pack(side=tk.LEFT)
        shredPassesEntry = ttk.Entry(shredFrame, width=5)
        shredPassesEntry.insert(0, "10")
        shredPassesEntry.pack(side=tk.LEFT, padx=5)
        
        shutdownFrame = ttk.LabelFrame(configFrame, text="Shutdown Options")
        shutdownFrame.pack(fill=tk.X, padx=10, pady=5)
        
        shutdownModeVar = tk.StringVar(value="immediate")
        ttk.Radiobutton(shutdownFrame, text="Immediate (shutdown -h now)", 
                       variable=shutdownModeVar, value="immediate").pack(anchor='w', padx=5, pady=2)
        ttk.Radiobutton(shutdownFrame, text="Forced (poweroff -f)", 
                       variable=shutdownModeVar, value="forced").pack(anchor='w', padx=5, pady=2)
        
        volumeFrame = ttk.LabelFrame(configFrame, text="USB Volume Dismounting")
        volumeFrame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(volumeFrame, text="Volumes to dismount (leave empty for all non-system USB volumes):").pack(anchor='w', padx=5, pady=2)
        volumeSelectionFrame = ttk.Frame(volumeFrame)
        volumeSelectionFrame.pack(fill=tk.X, padx=5, pady=2)
        volumesEntry = ttk.Entry(volumeSelectionFrame)
        volumesEntry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        volumeButton = ttk.Button(volumeSelectionFrame, text="Select Volumes", command=selectVolumes)
        volumeButton.pack(side=tk.LEFT, padx=5)
        
        taskFrame = ttk.LabelFrame(configFrame, text="Select Tasks to Execute")
        taskFrame.pack(fill=tk.X, padx=10, pady=10)

        tasks = []

        taskGrid = ttk.Frame(taskFrame)
        taskGrid.pack(fill=tk.X, padx=5, pady=5)

        taskDismount = tk.StringVar(value="Dismount VeraCrypt Volumes")
        taskDismountCheckbox = ttk.Checkbutton(taskGrid, text="Dismount VeraCrypt Volumes", 
                                                 variable=taskDismount, onvalue="Dismount VeraCrypt Volumes", offvalue="")
        taskDismountCheckbox.grid(row=0, column=0, sticky='w', padx=5, pady=2)
        tasks.append(taskDismount)
        
        taskDismountUsb = tk.StringVar(value="Dismount USB Volumes")
        taskDismountUsbCheckbox = ttk.Checkbutton(taskGrid, text="Dismount USB Volumes", 
                                                   variable=taskDismountUsb, onvalue="Dismount USB Volumes", offvalue="")
        taskDismountUsbCheckbox.grid(row=0, column=1, sticky='w', padx=5, pady=2)
        tasks.append(taskDismountUsb)

        taskEndProcess = tk.StringVar(value="End Process")
        taskEndProcessCheckbox = ttk.Checkbutton(taskGrid, text="End Process", 
                                                   variable=taskEndProcess, onvalue="End Process", offvalue="")
        taskEndProcessCheckbox.grid(row=1, column=0, sticky='w', padx=5, pady=2)
        tasks.append(taskEndProcess)

        taskDeleteFile = tk.StringVar(value="Delete File")
        taskDeleteFileCheckbox = ttk.Checkbutton(taskGrid, text="Delete File", 
                                                   variable=taskDeleteFile, onvalue="Delete File", offvalue="")
        taskDeleteFileCheckbox.grid(row=1, column=1, sticky='w', padx=5, pady=2)
        tasks.append(taskDeleteFile)

        taskOverwriteFile = tk.StringVar(value="Overwrite File")
        taskOverwriteFileCheckbox = ttk.Checkbutton(taskGrid, text="Overwrite File", 
                                                      variable=taskOverwriteFile, onvalue="Overwrite File", offvalue="")
        taskOverwriteFileCheckbox.grid(row=2, column=0, sticky='w', padx=5, pady=2)
        tasks.append(taskOverwriteFile)

        taskTurnOffScreen = tk.StringVar(value="Turn Off Screen")
        taskTurnOffScreenCheckbox = ttk.Checkbutton(taskGrid, text="Turn Off Screen", 
                                                       variable=taskTurnOffScreen, onvalue="Turn Off Screen", offvalue="")
        taskTurnOffScreenCheckbox.grid(row=2, column=1, sticky='w', padx=5, pady=2)
        tasks.append(taskTurnOffScreen)

        taskLockComputer = tk.StringVar(value="Lock Computer")
        taskLockComputerCheckbox = ttk.Checkbutton(taskGrid, text="Lock Computer", 
                                                     variable=taskLockComputer, onvalue="Lock Computer", offvalue="")
        taskLockComputerCheckbox.grid(row=3, column=0, sticky='w', padx=5, pady=2)
        tasks.append(taskLockComputer)

        taskShutdown = tk.StringVar(value="Shutdown")
        taskShutdownCheckbox = ttk.Checkbutton(taskGrid, text="Shutdown", 
                                                variable=taskShutdown, onvalue="Shutdown", offvalue="")
        taskShutdownCheckbox.grid(row=3, column=1, sticky='w', padx=5, pady=2)
        tasks.append(taskShutdown)

        processFrame = ttk.LabelFrame(configFrame, text="Process Management")
        processFrame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(processFrame, text="Processes to Kill:").pack(anchor='w', padx=5, pady=2)
        
        processEntriesFrame = ttk.Frame(processFrame)
        processEntriesFrame.pack(fill=tk.X, padx=5, pady=2)
        
        processEntries = []
        initialProcessEntry = ttk.Entry(processEntriesFrame)
        initialProcessEntry.pack(fill=tk.X, padx=5, pady=2)
        processEntries.append(initialProcessEntry)
        
        addProcessButton = ttk.Button(processFrame, text="Add More Processes", command=addProcessEntry)
        addProcessButton.pack(anchor='e', padx=5, pady=5)

        fileFrame = ttk.LabelFrame(configFrame, text="File Management")
        fileFrame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(fileFrame, text="Files to Delete/Overwrite:").pack(anchor='w', padx=5, pady=2)
        fileSelectionFrame = ttk.Frame(fileFrame)
        fileSelectionFrame.pack(fill=tk.X, padx=5, pady=2)
        fileEntry = ttk.Entry(fileSelectionFrame)
        fileEntry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        fileButton = ttk.Button(fileSelectionFrame, text="Select Files", command=selectFiles)
        fileButton.pack(side=tk.LEFT, padx=5)

        commandFrame = ttk.LabelFrame(configFrame, text="Custom Commands")
        commandFrame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(commandFrame, text="Commands to Execute:").pack(anchor='w', padx=5, pady=2)
        
        commandEntriesFrame = ttk.Frame(commandFrame)
        commandEntriesFrame.pack(fill=tk.X, padx=5, pady=2)
        
        commandEntries = []
        initialCommandEntry = ttk.Entry(commandEntriesFrame)
        initialCommandEntry.pack(fill=tk.X, padx=5, pady=2)
        commandEntries.append(initialCommandEntry)
        
        addCommandButton = ttk.Button(commandFrame, text="Add More Commands", command=addCommandEntry)
        addCommandButton.pack(anchor='e', padx=5, pady=5)

        monitorFrame = ttk.Frame(monitoringTab)
        monitorFrame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        identifierMonitorFrame = ttk.LabelFrame(monitorFrame, text="USB Identifier Monitoring")
        identifierMonitorFrame.pack(fill=tk.X, padx=10, pady=10)
        
        identifierButtonFrame = ttk.Frame(identifierMonitorFrame)
        identifierButtonFrame.pack(fill=tk.X, padx=5, pady=10)
        
        startButton = ttk.Button(identifierButtonFrame, text="Arm USB Identifier Monitor", command=onStartButtonClick)
        startButton.pack(side=tk.LEFT, padx=5)
        
        pauseButton = ttk.Button(identifierButtonFrame, text="Disarm (Press 5 Times)", 
                                  command=onPauseButtonClick, state=tk.DISABLED)
        pauseButton.pack(side=tk.LEFT, padx=5)
        
        statusLabel = ttk.Label(identifierMonitorFrame, text="Status: Not Armed")
        statusLabel.pack(fill=tk.X, padx=5, pady=5)

        usbMonitorFrame = ttk.LabelFrame(monitorFrame, text="USB Change Monitoring")
        usbMonitorFrame.pack(fill=tk.X, padx=10, pady=10)
        
        usbButtonFrame = ttk.Frame(usbMonitorFrame)
        usbButtonFrame.pack(fill=tk.X, padx=5, pady=10)
        
        usbStartButton = ttk.Button(usbButtonFrame, text="Arm USB Change Monitor", 
                                     command=onUsbStartButtonClick)
        usbStartButton.pack(side=tk.LEFT, padx=5)
        
        usbPauseButton = ttk.Button(usbButtonFrame, text="Disarm (Press 5 Times)", 
                                      command=onUsbPauseButtonClick, state=tk.DISABLED)
        usbPauseButton.pack(side=tk.LEFT, padx=5)
        
        usbStatusLabel = ttk.Label(usbMonitorFrame, text="Status: Not Armed")
        usbStatusLabel.pack(fill=tk.X, padx=5, pady=5)

        logFrame = ttk.Frame(logTab)
        logFrame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        logTextFrame = ttk.Frame(logFrame)
        logTextFrame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(logTextFrame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        logText = tk.Text(logTextFrame, wrap=tk.WORD, height=30, state=tk.DISABLED, 
                          yscrollcommand=scrollbar.set)
        logText.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.config(command=logText.yview)
        
        clearLogButton = ttk.Button(logFrame, text="Clear Log", 
                                     command=lambda: [logText.config(state=tk.NORMAL), 
                                                     logText.delete(1.0, tk.END), 
                                                     logText.config(state=tk.DISABLED)])
        clearLogButton.pack(side=tk.RIGHT, padx=5, pady=5)
        
        docsFrame = ttk.Frame(docsTab)
        docsFrame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        docsText = tk.Text(docsFrame, wrap=tk.WORD, height=30, padx=10, pady=10)
        docsText.pack(fill=tk.BOTH, expand=True)
        
        docsContent = """USB Killswitch Documentation

OVERVIEW:
USB Killswitch is a security tool that monitors USB devices and performs configured actions when 
specific USB events occur, such as a device being removed or any USB device change.

MONITORING MODES:
1. USB Identifier Monitoring - Triggers actions when a specific USB drive (identified by name) is removed
2. USB Change Monitoring - Triggers actions when any USB device change is detected

CONFIGURATION OPTIONS:

- USB Identifier: The name of the USB drive to monitor (default: "K")
- VeraCrypt Timeout: Maximum time (in seconds) to wait for VeraCrypt volumes to dismount
- USB Dismount Timeout: Maximum time (in seconds) to wait for USB volumes to dismount
- Shred Overwrites: Number of passes when securely overwriting files
- Shutdown Options: Choose between immediate or forced shutdown
- Volumes to Dismount: Specify which volumes to dismount, or leave empty for all non-system USB volumes

AVAILABLE TASKS:
- Dismount VeraCrypt Volumes: Safely dismounts all VeraCrypt encrypted volumes
- Dismount USB Volumes: Safely dismounts USB drives
- End Process: Terminates specified processes
- Delete File: Deletes specified files
- Overwrite File: Securely overwrites files using the shred command
- Turn Off Screen: Turns off the display
- Lock Computer: Locks the computer screen
- Shutdown: Shuts down the system (runs last after all other tasks)

FAILSAFES AND EDGE CASES:
- All operations have timeouts to prevent hanging
- Each task is handled separately so failure in one won't stop others
- Multiple methods are tried for screen locking and turning off the display
- Secure dismounting of volumes with fallback to lazy unmount if needed
- System volumes are protected from accidental dismounting
- Custom commands run with timeouts to prevent hanging

REQUIREMENTS:
- Linux operating system
- Root privileges for some features (shutdown, some dismount operations)
- VeraCrypt installed for VeraCrypt volume dismounting

USAGE TIPS:
- For maximum security, combine multiple actions
- Test your configuration before relying on it in critical situations
- The 5-press disarm feature prevents accidental disarming
- Custom commands can extend functionality for specific needs

This project is still in development. Please report bugs or contribute at:
https://github.com/nthpyrodev/usb-killswitch
"""
        docsText.insert(tk.END, docsContent)
        docsText.config(state=tk.DISABLED)

        logMessage("USB Killswitch Monitor started. Configure and arm to begin monitoring.")

        notebook.focus_set()

        root.mainloop()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create GUI: {str(e)}")

def launchGuiWithElevatedPrivileges():
    try:
        if os.geteuid() == 0:
            createGui()
        else:
            try:
                subprocess.run(['sudo', sys.executable] + sys.argv)
            except Exception as e:
                messagebox.showwarning("Warning", 
                    f"Some features may require root privileges. Consider running with sudo.\nError: {str(e)}")
                createGui()
    except Exception as e:
        print(f"Error launching application: {str(e)}")
        createGui()

launchGuiWithElevatedPrivileges()
