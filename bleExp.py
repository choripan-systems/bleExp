#! /usr/bin/python3

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import asyncio
import threading
from bleak import BleakScanner, BleakClient
from typing import Optional
from datetime import datetime
import argparse

class BLEScanner:
    def __init__(self, root, cmdArgs):
        self.root = root
        self.root.title("BLE Device Explorer")
        self.root.geometry("1000x1080")
        
        # Set custom icon if available
        try:
            iconPath = "bleExp.png"
            iconImage = tk.PhotoImage(file=iconPath)
            self.root.iconphoto(True, iconImage)
        except Exception as e:
            # Icon file not found or error loading - continue without icon
            pass
        
        self.client: Optional[BleakClient] = None
        self.scanning = False
        self.readableCharacteristics = {}  # Store readable characteristics
        self.writableCharacteristics = {}  # Store writable characteristics
        self.notifiableCharacteristics = {}  # Store notifiable/indicatable characteristics
        self.activeNotifications = {}  # Track active notifications
        self.loop = None  # Store the event loop
        self.discoveredDevices = []  # Store discovered devices
        self.deviceAdvData = {}  # Store advertisement data

        # Command line arguments
        self.serviceUuid = cmdArgs.svc_uuid
        self.deviceNamePrefix = cmdArgs.dev_name_prefix
        self.scanDuration = cmdArgs.scan_duration
        self.logFile = cmdArgs.log_file
        self.logFileHandle = None
        self.textFontSize = cmdArgs.text_font_size
        
        # Open log file if specified
        if self.logFile:
            try:
                self.logFileHandle = open(self.logFile, 'a', encoding='utf-8')
                self._write_to_log_file(f"\n{'='*80}\n")
                self._write_to_log_file(f"BLE Explorer Log - Session started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                self._write_to_log_file(f"{'='*80}\n")
            except Exception as e:
                print(f"Warning: Could not open log file '{self.logFile}': {e}")
                self.logFileHandle = None
        
        # Create UI
        self.createWidgets()
        
    def createWidgets(self):
        # Top frame for UUID input and scan button
        topFrame = ttk.Frame(self.root, padding="10")
        topFrame.pack(fill=tk.X)
        
        ttk.Label(topFrame, text="Service UUID:").pack(side=tk.LEFT, padx=5)
        self.serviceUuidEntry = ttk.Entry(topFrame, width=20)
        if self.serviceUuid:
            self.serviceUuidEntry.insert(0, self.serviceUuid)
        self.serviceUuidEntry.pack(side=tk.LEFT, padx=5)

        ttk.Label(topFrame, text="Device Name Prefix:").pack(side=tk.LEFT, padx=(20, 5))
        self.deviceNamePrefixEntry = ttk.Entry(topFrame, width=15)
        if self.deviceNamePrefix:
            self.deviceNamePrefixEntry.insert(0, self.deviceNamePrefix)
        self.deviceNamePrefixEntry.pack(side=tk.LEFT, padx=5)        
        
        ttk.Label(topFrame, text="Scan Duration:").pack(side=tk.LEFT, padx=(20, 5))
        self.scanDurationEntry = ttk.Entry(topFrame, width=6)
        self.scanDurationEntry.insert(0, self.scanDuration)
        self.scanDurationEntry.pack(side=tk.LEFT, padx=5)
        
        self.scanButton = ttk.Button(topFrame, text="Start Scan", command=self.toggleScan)
        self.scanButton.pack(side=tk.LEFT, padx=5)
        
        self.statusLabel = ttk.Label(topFrame, text="Ready", foreground="blue")
        self.statusLabel.pack(side=tk.LEFT, padx=20)
        
        # Separator
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # Device list frame
        devicesFrame = ttk.LabelFrame(self.root, text="Discovered Devices", padding="10")
        devicesFrame.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)
        
        # Create listbox with scrollbar
        listContainer = ttk.Frame(devicesFrame)
        listContainer.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(listContainer, orient=tk.VERTICAL)
        self.deviceListbox = tk.Listbox(
            listContainer,
            height=6,
            font=("Consolas", self.textFontSize),
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.deviceListbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.deviceListbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Connect button for selected device
        buttonsFrame = ttk.Frame(devicesFrame)
        buttonsFrame.pack(fill=tk.X, pady=(5, 0))
        
        self.showAdvDataButton = ttk.Button(
            buttonsFrame,
            text="Show Advertisement Data",
            command=self.showAdvertisementData,
            state=tk.DISABLED
        )
        self.showAdvDataButton.pack(side=tk.LEFT, padx=5)

        self.connectButton = ttk.Button(
            buttonsFrame,
            text="Connect to Selected Device",
            command=self.connectToSelected,
            state=tk.DISABLED
        )
        self.connectButton.pack(side=tk.LEFT, padx=5)

        style = ttk.Style()
        style.configure("Red.TButton", foreground="red")

        self.disconnectButton = ttk.Button(
            buttonsFrame,
            text="Disconnect",
            style="Red.TButton",
            command=self.disconnectFromDevice,
            state=tk.DISABLED
        )
        self.disconnectButton.pack(side=tk.RIGHT, padx=5)
        
        # Separator
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # Main output area
        outputDataFrame = ttk.Frame(self.root, padding="10")
        outputDataFrame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(outputDataFrame, text="Device Information:").pack(anchor=tk.W)
        
        self.outputText = scrolledtext.ScrolledText(
            outputDataFrame, 
            wrap=tk.WORD, 
            width=100, 
            height=20,
            font=("Consolas", self.textFontSize)
        )
        self.outputText.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Read characteristic frame
        readCharFrame = ttk.LabelFrame(self.root, text="Read Characteristic", padding="10")
        readCharFrame.pack(fill=tk.X, padx=10, pady=5)
        
        # Characteristic UUID for reading
        ttk.Label(readCharFrame, text="Char UUID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.readCharUuidEntry = ttk.Entry(readCharFrame, width=40)
        self.readCharUuidEntry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Read button
        self.readCharButton = ttk.Button(
            readCharFrame, 
            text="Read Value", 
            command=self.readCharacteristic,
            state=tk.DISABLED
        )
        self.readCharButton.grid(row=1, column=1, sticky=tk.E, padx=5, pady=5)
        
        # Configure grid weights
        readCharFrame.columnconfigure(1, weight=1)
        
        # Write characteristic frame
        writeCharFrame = ttk.LabelFrame(self.root, text="Write to Characteristic", padding="10")
        writeCharFrame.pack(fill=tk.X, padx=10, pady=5)
        
        # Characteristic UUID
        ttk.Label(writeCharFrame, text="Char UUID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.writeCharUuidEntry = ttk.Entry(writeCharFrame, width=40)
        self.writeCharUuidEntry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Value type selection
        ttk.Label(writeCharFrame, text="Value Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        type_frame = ttk.Frame(writeCharFrame)
        type_frame.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        self.value_type = tk.StringVar(value="hex")
        ttk.Radiobutton(type_frame, text="Hex", variable=self.value_type, value="hex").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Decimal", variable=self.value_type, value="dec").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="UTF-8 String", variable=self.value_type, value="string").pack(side=tk.LEFT, padx=5)
        
        # Value input
        ttk.Label(writeCharFrame, text="Value:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.write_value_entry = ttk.Entry(writeCharFrame, width=40)
        self.write_value_entry.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Write button
        self.writeCharButton = ttk.Button(
            writeCharFrame, 
            text="Write Value", 
            command=self.writeCharacteristic,
            state=tk.DISABLED
        )
        self.writeCharButton.grid(row=3, column=1, sticky=tk.E, padx=5, pady=5)
        
        # Configure grid weights
        writeCharFrame.columnconfigure(1, weight=1)
        
        # Notification/Indication frame
        notifyCharFrame = ttk.LabelFrame(self.root, text="Notifications/Indications", padding="10")
        notifyCharFrame.pack(fill=tk.X, padx=10, pady=5)
        
        # Characteristic UUID for notifications
        ttk.Label(notifyCharFrame, text="Char UUID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.notifyCharUuidEntry = ttk.Entry(notifyCharFrame, width=40)
        self.notifyCharUuidEntry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Notification buttons
        buttonsFrame = ttk.Frame(notifyCharFrame)
        buttonsFrame.grid(row=1, column=1, sticky=tk.E, padx=5, pady=5)
        
        self.notifyCharEnableButton = ttk.Button(
            buttonsFrame, 
            text="Enable Notifications", 
            command=self.enableCharNotifications,
            state=tk.DISABLED
        )
        self.notifyCharEnableButton.pack(side=tk.LEFT, padx=5)
        
        self.notifyCharDisableButton = ttk.Button(
            buttonsFrame, 
            text="Disable Notifications", 
            command=self.disableCharNotifications,
            state=tk.DISABLED
        )
        self.notifyCharDisableButton.pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        notifyCharFrame.columnconfigure(1, weight=1)
        
    def log(self, message):
        """Thread-safe logging to the text widget"""
        self.root.after(0, self._log_impl, message)
        
    def _log_impl(self, message):
        self.outputText.insert(tk.END, message + "\n")
        self.outputText.see(tk.END)
        # Write to log file if enabled
        if self.logFileHandle:
            self._write_to_log_file(message + "\n")
            
    def _write_to_log_file(self, text):
        """Write text to log file and flush immediately"""
        try:
            self.logFileHandle.write(text)
            self.logFileHandle.flush()
        except Exception as e:
            print(f"Error writing to log file: {e}")
        
    def updateStatus(self, message, color="blue"):
        """Update status label"""
        self.root.after(0, lambda: self.statusLabel.config(text=message, foreground=color))
        
    def _enable_read_button(self):
        """Enable the read button (must be called from main thread)"""
        self.readCharButton.config(state=tk.NORMAL)
        
    def _enable_write_button(self):
        """Enable the write button (must be called from main thread)"""
        self.writeCharButton.config(state=tk.NORMAL)
        
    def _enable_notify_buttons(self):
        """Enable the notification buttons (must be called from main thread)"""
        self.notifyCharEnableButton.config(state=tk.NORMAL)
        self.notifyCharDisableButton.config(state=tk.NORMAL)
        
    def toggleScan(self):
        if not self.scanning:
            self.startScan()
        else:
            self.stopScan()
            
    def startScan(self):
        # Get the device match filters
        svcUuidFilter = self.serviceUuidEntry.get().strip().replace("-", "").replace(" ", "")
        devNameFilter = self.deviceNamePrefixEntry.get().strip()
        
        # At least one filter must be specified
        #if not svcUuidFilter and not devNameFilter:
        #    messagebox.showerror("Error", "Please enter a Service Data UUID or a Device Name Prefix (or both)")
        #    return
        
        # Validate UUID if provided
        uuidType = None
        if svcUuidFilter:
            try:
                int(svcUuidFilter, 16)
            except ValueError:
                messagebox.showerror("Error", "Invalid hex UUID")
                return
            
            # Determine if it's a 16-bit or 128-bit UUID
            if len(svcUuidFilter) == 4:
                uuidType = "16-bit"
            elif len(svcUuidFilter) == 32:
                uuidType = "128-bit"
            else:
                messagebox.showerror("Error", "UUID must be 4 hex digits (16-bit) or 32 hex digits (128-bit)")
                return
        
        # Validate scan duration
        try:
            scanDuration = float(self.scanDurationEntry.get().strip())
            if scanDuration <= 0:
                messagebox.showerror("Error", "Scan duration must be positive")
                return
        except ValueError:
            messagebox.showerror("Error", "Invalid scan duration")
            return
            
        self.scanning = True
        self.scanButton.config(text="Stop Scan")
        self.serviceUuidEntry.config(state=tk.DISABLED)
        self.deviceNamePrefixEntry.config(state=tk.DISABLED)
        self.scanDurationEntry.config(state=tk.DISABLED)
        self.outputText.delete(1.0, tk.END)
        
        # Run scan in separate thread
        thread = threading.Thread(target=self.runScan, args=(svcUuidFilter, uuidType, devNameFilter, scanDuration), daemon=True)
        thread.start()
        
    def stopScan(self):
        self.scanning = False
        self.scanButton.config(text="Start Scan")
        self.serviceUuidEntry.config(state=tk.NORMAL)
        self.deviceNamePrefixEntry.config(state=tk.NORMAL)
        self.scanDurationEntry.config(state=tk.NORMAL)
        self.updateStatus("Scan stopped", "orange")
        
    def runScan(self, svcUuidFilter, uuidType, devNameFilter, scanDuration):
        """Run the BLE scan in an asyncio event loop"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.scanForDevices(svcUuidFilter, uuidType, devNameFilter, scanDuration))
        except Exception as e:
            self.log(f"Error: {str(e)}")
            self.updateStatus(f"Error: {str(e)}", "red")
        finally:
            self.loop.close()
            self.loop = None
            
    async def scanForDevices(self, svcUuidFilter, uuidType, devNameFilter, scanDuration):
        """Scan for BLE devices with the specified UUID and/or name prefix"""
        # Convert to full 128-bit UUID if needed
        full_uuid = None
        if svcUuidFilter:
            if uuidType == "16-bit":
                full_uuid = f"0000{svcUuidFilter.lower()}-0000-1000-8000-00805f9b34fb"
            else:
                # Format 128-bit UUID with dashes
                uuid_lower = svcUuidFilter.lower()
                full_uuid = f"{uuid_lower[0:8]}-{uuid_lower[8:12]}-{uuid_lower[12:16]}-{uuid_lower[16:20]}-{uuid_lower[20:32]}"
        
        # Log scan criteria
        self.log(f"Scanning for devices matching:")
        if svcUuidFilter:
            self.log(f"  Advertised Service UUID: {svcUuidFilter}")
            #self.log(f"  UUID Type: {uuidType}")
            #self.log(f"  Full UUID: {full_uuid}")
        if devNameFilter:
            self.log(f"  Device Name Prefix: '{devNameFilter}'")
        self.log(f"Scan duration: {scanDuration} seconds")
        self.log("-" * 80)
        self.updateStatus("Scanning...", "green")
        
        matchingDevices = []
        deviceAdvData = {}  # Store advertisement data for each device
        
        def detectionCallback(device, advertisement_data):
            """Called when a device is detected"""

            # Check if device matches UUID filter (if specified)
            uuidMatch = True  # Default to True if no UUID filter
            if full_uuid:
                uuidMatch = False
                if advertisement_data.service_uuids:
                    adv_uuids = [u.lower() for u in advertisement_data.service_uuids]
                    uuidMatch = full_uuid in adv_uuids
            
            # Check if device matches name prefix filter (if specified)
            nameMatch = True  # Default to True if no name filter
            if devNameFilter:
                device_name = device.name or ""
                nameMatch = device_name.startswith(devNameFilter)
            
            # Device must match both filters (if both are specified)
            if uuidMatch and nameMatch:
                # Avoid duplicates
                if not any(d.address == device.address for d in matchingDevices):
                    matchingDevices.append(device)
                    deviceAdvData[device.address] = advertisement_data
                    self.log(f"Found: {device.name or 'Unknown'} ({device.address})")
        
        try:
            # Create scanner with callback
            scanner = BleakScanner(detection_callback=detectionCallback)
            
            # Start scanning
            await scanner.start()
            await asyncio.sleep(scanDuration)
            await scanner.stop()
            
            if not self.scanning:
                return
            
            if not matchingDevices:
                self.log(f"\nNo devices found matching the specified criteria")
                self.log("Note: The device must match all specified filters (UUID and/or name prefix)")
                self.updateStatus("No matching devices found", "orange")
                self.scanning = False
                self.root.after(0, lambda: self.scanButton.config(text="Start Scan"))
                self.root.after(0, lambda: self.serviceUuidEntry.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.deviceNamePrefixEntry.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.scanDurationEntry.config(state=tk.NORMAL))
                return
            
            # Store discovered devices and advertisement data
            self.discoveredDevices = matchingDevices
            self.deviceAdvData = deviceAdvData
            
            self.log(f"\nFound {len(matchingDevices)} matching device(s)\n")
            
            # Populate device list
            self.root.after(0, self._populate_device_list)
            self.updateStatus(f"Found {len(matchingDevices)} device(s) - Select one to connect", "blue")
            
        except Exception as e:
            self.log(f"\nScan error: {str(e)}")
            self.updateStatus(f"Error: {str(e)}", "red")
        finally:
            self.scanning = False
            self.root.after(0, lambda: self.scanButton.config(text="Start Scan"))
            self.root.after(0, lambda: self.serviceUuidEntry.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.deviceNamePrefixEntry.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.scanDurationEntry.config(state=tk.NORMAL))
            
    def _populate_device_list(self):
        """Populate the device listbox (must be called from main thread)"""
        self.deviceListbox.delete(0, tk.END)
        for device in self.discoveredDevices:
            devName = f"{device.name or 'Unknown':30s} [{device.address}]"
            self.deviceListbox.insert(tk.END, devName)
        
        if self.discoveredDevices:
            self.connectButton.config(state=tk.NORMAL)
            self.showAdvDataButton.config(state=tk.NORMAL)
            self.deviceListbox.selection_set(0)  # Select first device by default
            
    def connectToSelected(self):
        """Connect to the device selected in the listbox"""
        selection = self.deviceListbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a device from the list")
            return
        
        devIndex = selection[0]
        device = self.discoveredDevices[devIndex]
        
        self.outputText.delete(1.0, tk.END)
        self.log(f"Connecting to: {device.name or 'Unknown'} ({device.address})")
        self.updateStatus(f"Connecting to {device.address}...", "green")
        
        # Disable buttons during connection
        self.connectButton.config(state=tk.DISABLED)
        self.showAdvDataButton.config(state=tk.DISABLED)
        
        # Run connection in separate thread
        thread = threading.Thread(target=self.runConnect, args=(device,), daemon=True)
        thread.start()
        
    def runConnect(self, device):
        """Run the connection in an asyncio event loop"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.connect_and_explore(device))
        except Exception as e:
            self.log(f"Connection error: {str(e)}")
            self.updateStatus(f"Error: {str(e)}", "red")
        finally:
            self.loop.close()
            self.loop = None
            
    def showAdvertisementData(self):
        """Show detailed advertisement data for selected device"""
        selection = self.deviceListbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a device from the list")
            return
        
        devIndex = selection[0]
        device = self.discoveredDevices[devIndex]
        advData = self.deviceAdvData.get(device.address)
        
        self.outputText.delete(1.0, tk.END)
        
        if advData:
            self.log(f"{'=' * 80}")
            self.log(f"Device: {device.name or 'Unknown'}")
            self.log(f"Address: {device.address}")
            self.log(f"\nAdvertisement Data:")
            
            # Local name
            if advData.local_name:
                self.log(f"    Local Name: {advData.local_name}")
            
            # RSSI
            if advData.rssi is not None:
                self.log(f"    RSSI: {advData.rssi} dBm")
            
            # TX Power
            if advData.tx_power is not None:
                self.log(f"    TX Power: {advData.tx_power} dBm")
            
            # Service UUIDs
            if advData.service_uuids:
                self.log(f"    Service UUIDs ({len(advData.service_uuids)}):")
                for uuid in advData.service_uuids:
                    self.log(f"        - {uuid}")
            
            # Service Data
            if advData.service_data:
                self.log(f"    Service Data ({len(advData.service_data)} entries):")
                for uuid, data in advData.service_data.items():
                    hex_data = " ".join(f"{b:02x}" for b in data)
                    self.log(f"        {uuid}: {hex_data}")
            
            # Manufacturer Data
            if advData.manufacturer_data:
                self.log(f"    Manufacturer Data ({len(advData.manufacturer_data)} entries):")
                for company_id, data in advData.manufacturer_data.items():
                    hex_data = " ".join(f"{b:02x}" for b in data)
                    self.log(f"        Company ID 0x{company_id:04x}: {hex_data}")
            
            # Platform specific data
            if hasattr(advData, 'platform_data'):
                platform_data = advData.platform_data
                
                # Appearance (if available)
                if hasattr(platform_data, 'appearance') and platform_data.appearance is not None:
                    self.log(f"    Appearance: 0x{platform_data.appearance:04x}")
                
                # Flags (if available)
                if hasattr(platform_data, 'flags') and platform_data.flags is not None:
                    self.log(f"    Flags: 0x{platform_data.flags:02x}")
            
            self.log(f"{'=' * 80}")
        else:
            self.log("No advertisement data available for this device")
            
    async def connect_and_explore(self, device):
        """Connect to device and read all services/characteristics"""
        try:
            self.client = BleakClient(device.address)
            await self.client.connect()
            
            self.root.after(0, lambda: self.disconnectButton.config(state=tk.NORMAL))
            
            if not self.client.is_connected:
                self.log("Failed to connect")
                return
                
            self.log("Connected successfully!\n")
            self.updateStatus("Connected - Reading services...", "green")
            
            # Get all services
            services = self.client.services
            service_list = list(services)
            # Sort services by UUID
            service_list.sort(key=lambda s: s.uuid)
            self.log(f"Device has {len(service_list)} service(s):\n")
            self.log("=" * 80)

            self.readableCharacteristics.clear()            
            self.writableCharacteristics.clear()
            self.notifiableCharacteristics.clear()
            
            for service in service_list:
                self.log(f"\nService: {service.uuid}")
                self.log(f"    Description: {service.description}")
                self.log(f"    Characteristics: {len(service.characteristics)}")
                
                # Sort characteristics by UUID
                char_list = sorted(service.characteristics, key=lambda c: c.uuid)
                
                for char in char_list:
                    self.log(f"\n    Characteristic: {char.uuid}")
                    self.log(f"        Description: {char.description}")
                    self.log(f"        Properties: {', '.join(char.properties)}")
                    
                    # Store readable characteristics
                    if "read" in char.properties:
                        self.readableCharacteristics[char.uuid] = char
                                            
                    # Store writable characteristics
                    if "write" in char.properties or "write-without-response" in char.properties:
                        self.writableCharacteristics[char.uuid] = char
                    
                    # Store notifiable/indicatable characteristics
                    if "notify" in char.properties or "indicate" in char.properties:
                        self.notifiableCharacteristics[char.uuid] = char
                    
                    # Read characteristic if readable
                    if "read" in char.properties:
                        try:
                            value = await self.client.read_gatt_char(char.uuid)
                            # Format value as hex
                            hex_value = " ".join(f"{b:02x}" for b in value)
                            self.log(f"        Value (hex): {hex_value}")
                            # Try to decode as string
                            try:
                                str_value = value.decode('utf-8', errors='ignore')
                                if str_value.isprintable():
                                    self.log(f"        Value (string): {str_value}")
                            except:
                                pass
                        except Exception as e:
                            self.log(f"        Read error: {str(e)}")
                    
                    # List descriptors
                    #if char.descriptors:
                    #    self.log(f"        Descriptors: {len(char.descriptors)}")
                    #    for desc in char.descriptors:
                    #        self.log(f"            - {desc.uuid}")
                            
            self.log("\n" + "=" * 80)
            self.log("\nExploration complete!")
            
            if self.readableCharacteristics:
                self.log(f"Found {len(self.readableCharacteristics)} readable characteristic(s)")
                self.root.after(0, self._enable_read_button)
                            
            if self.writableCharacteristics:
                self.log(f"\nFound {len(self.writableCharacteristics)} writable characteristic(s)")
                self.root.after(0, self._enable_write_button)
            
            if self.notifiableCharacteristics:
                self.log(f"Found {len(self.notifiableCharacteristics)} notifiable/indicatable characteristic(s)")
                self.root.after(0, self._enable_notify_buttons)
            
            self.updateStatus("Connected and ready", "blue")
            
            # Keep the loop running for write operations
            while self.client and self.client.is_connected:
                await asyncio.sleep(0.1)
            
        except Exception as e:
            self.log(f"\nConnection error: {str(e)}")
            self.updateStatus(f"Error: {str(e)}", "red")
            if self.client and self.client.is_connected:
                await self.client.disconnect()
            self.client = None
            self.readableCharacteristics.clear()
            self.writableCharacteristics.clear()
            self.notifiableCharacteristics.clear()
            self.activeNotifications.clear()
            self.root.after(0, lambda: self.disconnectButton.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.readCharButton.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.writeCharButton.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.notifyCharEnableButton.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.notifyCharDisableButton.config(state=tk.DISABLED))
            
    def disconnectFromDevice(self):
        """Disconnect from the current device"""
        if self.client:
            thread = threading.Thread(target=self.runDisconnect, daemon=True)
            thread.start()
            
    def runDisconnect(self):
        """Run disconnect in asyncio loop"""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.asyncDisconnect(), self.loop)
        else:
            # Fallback if loop is not available
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.asyncDisconnect())
            finally:
                loop.close()
            
    async def asyncDisconnect(self):
        """Disconnect from device"""
        try:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
                self.log("\nDisconnected")
        except Exception as e:
            self.log(f"\nDisconnect error: {str(e)}")
        finally:
            self.client = None
            self.readableCharacteristics.clear()
            self.writableCharacteristics.clear()
            self.notifiableCharacteristics.clear()
            self.activeNotifications.clear()
            self.updateStatus("Disconnected", "orange")
            self.root.after(0, lambda: self.disconnectButton.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.readCharButton.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.writeCharButton.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.notifyCharEnableButton.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.notifyCharDisableButton.config(state=tk.DISABLED))

    def readCharacteristic(self):
        """Manually read a characteristic value"""
        if not self.client:
            messagebox.showerror("Error", "Not connected to a device")
            return
            
        uuid = self.readCharUuidEntry.get().strip()
        if not uuid:
            messagebox.showerror("Error", "Please enter a characteristic UUID")
            return
        
        # Schedule the read operation in the same event loop
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.read_char_value(uuid),
                self.loop
            )
        else:
            messagebox.showerror("Error", "Event loop not available")
            
    async def read_char_value(self, uuid):
        """Read a characteristic value"""
        try:
            # Normalize UUID
            uuid_normalized = self.normalize_uuid(uuid)
            
            # Check if this characteristic supports reading
            if uuid_normalized not in self.readableCharacteristics:
                self.log(f"\nError: Characteristic {uuid} does not support reading or not found")
                return
            
            # Read the characteristic
            self.log(f"\nReading characteristic {uuid}...")
            self.updateStatus("Reading...", "green")
            
            value = await self.client.read_gatt_char(uuid_normalized)
            
            # Format value as hex
            hex_value = " ".join(f"{b:02x}" for b in value)
            self.log(f"  Value (hex): {hex_value}")
            self.log(f"  Length: {len(value)} byte(s)")
            
            # Try to decode as string
            try:
                str_value = value.decode('utf-8', errors='ignore')
                if str_value.isprintable():
                    self.log(f"  Value (string): {str_value}")
            except:
                pass
            
            # Try to decode as integer (if 1, 2, or 4 bytes)
            if len(value) == 1:
                self.log(f"  Value (uint8): {value[0]}")
            elif len(value) == 2:
                uint16_le = int.from_bytes(value, byteorder='little')
                uint16_be = int.from_bytes(value, byteorder='big')
                self.log(f"  Value (uint16 LE): {uint16_le}")
                self.log(f"  Value (uint16 BE): {uint16_be}")
            elif len(value) == 4:
                uint32_le = int.from_bytes(value, byteorder='little')
                uint32_be = int.from_bytes(value, byteorder='big')
                self.log(f"  Value (uint32 LE): {uint32_le}")
                self.log(f"  Value (uint32 BE): {uint32_be}")
            
            self.log("Read successful!")
            self.updateStatus("Read complete", "blue")
            
        except Exception as e:
            self.log(f"\nRead failed: {str(e)}")
            self.updateStatus(f"Read failed: {str(e)}", "red")
            
    def writeCharacteristic(self):
        """Write a value to a characteristic"""
        if not self.client:
            messagebox.showerror("Error", "Not connected to a device")
            return
            
        uuid = self.writeCharUuidEntry.get().strip()
        if not uuid:
            messagebox.showerror("Error", "Please enter a characteristic UUID")
            return
            
        value_str = self.write_value_entry.get().strip()
        if not value_str:
            messagebox.showerror("Error", "Please enter a value to write")
            return
        
        # Schedule the write operation in the same event loop
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.write_value(uuid, value_str, self.value_type.get()),
                self.loop
            )
        else:
            messagebox.showerror("Error", "Event loop not available")
    
    def run_write(self, uuid, value_str, value_type):
        """Deprecated - no longer used"""
        pass
            
    async def write_value(self, uuid, value_str, value_type):
        """Write a value to a characteristic"""
        try:
            # Normalize UUID
            uuid_normalized = self.normalize_uuid(uuid)
            
            # Check if this is a writable characteristic
            if uuid_normalized not in self.writableCharacteristics:
                self.log(f"\nError: Characteristic {uuid} is not writable or not found")
                return
                
            # Parse the value based on type
            if value_type == "hex":
                # Parse hex string (e.g., "01 02 03" or "010203")
                hex_str = value_str.replace(" ", "").replace("0x", "")
                if len(hex_str) % 2 != 0:
                    self.log("\nError: Hex string must have even number of characters")
                    return
                try:
                    data = bytes.fromhex(hex_str)
                except ValueError as e:
                    self.log(f"\nError: Invalid hex string: {e}")
                    return
                    
            elif value_type == "dec":
                # Parse decimal values (comma or space separated)
                try:
                    values = [int(v.strip()) for v in value_str.replace(",", " ").split()]
                    if any(v < 0 or v > 255 for v in values):
                        self.log("\nError: Decimal values must be between 0 and 255")
                        return
                    data = bytes(values)
                except ValueError as e:
                    self.log(f"\nError: Invalid decimal values: {e}")
                    return
                    
            elif value_type == "string":
                # Encode string as UTF-8
                data = value_str.encode('utf-8')
            else:
                self.log(f"\nError: Unknown value type: {value_type}")
                return
                
            # Write to characteristic
            self.log(f"\nWriting to characteristic {uuid}...")
            self.log(f"  Value type: {value_type}")
            self.log(f"  Bytes: {' '.join(f'{b:02x}' for b in data)}")
            self.updateStatus("Writing...", "green")
            
            await self.client.write_gatt_char(uuid_normalized, data)
            
            self.log("Write successful!")
            self.updateStatus("Write complete", "blue")
            
        except Exception as e:
            self.log(f"\nWrite failed: {str(e)}")
            self.updateStatus(f"Write failed: {str(e)}", "red")
            
    def enableCharNotifications(self):
        """Enable notifications/indications for a characteristic"""
        if not self.client:
            messagebox.showerror("Error", "Not connected to a device")
            return
            
        uuid = self.notifyCharUuidEntry.get().strip()
        if not uuid:
            messagebox.showerror("Error", "Please enter a characteristic UUID")
            return
        
        # Schedule the enable operation in the same event loop
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.startNotify(uuid),
                self.loop
            )
        else:
            messagebox.showerror("Error", "Event loop not available")
            
    def disableCharNotifications(self):
        """Disable notifications/indications for a characteristic"""
        if not self.client:
            messagebox.showerror("Error", "Not connected to a device")
            return
            
        uuid = self.notifyCharUuidEntry.get().strip()
        if not uuid:
            messagebox.showerror("Error", "Please enter a characteristic UUID")
            return
        
        # Schedule the disable operation in the same event loop
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.stopNotify(uuid),
                self.loop
            )
        else:
            messagebox.showerror("Error", "Event loop not available")
            
    async def startNotify(self, uuid):
        """Start notifications/indications for a characteristic"""
        try:
            # Normalize UUID
            uuid_normalized = self.normalize_uuid(uuid)
            
            # Check if this characteristic supports notifications/indications
            if uuid_normalized not in self.notifiableCharacteristics:
                self.log(f"\nError: Characteristic {uuid} does not support notifications/indications")
                return
            
            # Check if already subscribed
            if uuid_normalized in self.activeNotifications:
                self.log(f"\nNotifications already enabled for {uuid}")
                return
            
            # Define notification callback
            def notification_handler(sender, data):
                hex_value = " ".join(f"{b:02x}" for b in data)
                timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
                self.log(f"[{timestamp}] [NOTIFY] {uuid}: {hex_value}")
                # Try to decode as string
                try:
                    str_value = data.decode('utf-8', errors='ignore')
                    if str_value.isprintable():
                        self.log(f"{' ' * (len(timestamp) + 2)}         String: {str_value}")
                except:
                    pass
            
            # Start notifications
            self.log(f"\nEnabling notifications for {uuid}...")
            await self.client.start_notify(uuid_normalized, notification_handler)
            self.activeNotifications[uuid_normalized] = True
            self.log("Notifications enabled!")
            self.updateStatus("Notifications enabled", "blue")
            
        except Exception as e:
            self.log(f"\nFailed to enable notifications: {str(e)}")
            self.updateStatus(f"Notification error: {str(e)}", "red")
            
    async def stopNotify(self, uuid):
        """Stop notifications/indications for a characteristic"""
        try:
            # Normalize UUID
            uuid_normalized = self.normalize_uuid(uuid)
            
            # Check if notifications are active
            if uuid_normalized not in self.activeNotifications:
                self.log(f"\nNo active notifications for {uuid}")
                return
            
            # Stop notifications
            self.log(f"\nDisabling notifications for {uuid}...")
            await self.client.stop_notify(uuid_normalized)
            del self.activeNotifications[uuid_normalized]
            self.log("Notifications disabled!")
            self.updateStatus("Notifications disabled", "blue")
            
        except Exception as e:
            self.log(f"\nFailed to disable notifications: {str(e)}")
            self.updateStatus(f"Notification error: {str(e)}", "red")
            
    def normalize_uuid(self, uuid):
        """Normalize UUID to full 128-bit format with lowercase"""
        # Remove spaces and dashes
        uuid_clean = uuid.replace("-", "").replace(" ", "").lower()
        
        # Check length
        if len(uuid_clean) == 4:
            # 16-bit UUID - convert to 128-bit
            return f"0000{uuid_clean}-0000-1000-8000-00805f9b34fb"
        elif len(uuid_clean) == 32:
            # 128-bit UUID - format with dashes
            return f"{uuid_clean[0:8]}-{uuid_clean[8:12]}-{uuid_clean[12:16]}-{uuid_clean[16:20]}-{uuid_clean[20:32]}"
        else:
            # Return as-is and let it fail with proper error message
            return uuid.lower()
            
def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="BLE Device Explorer - Scan and connect to Bluetooth Low Energy devices")
    parser.add_argument(
        '--svc-uuid',
        type=str,
        default=None,
        help="Advertised Service UUID to match"
    )
    parser.add_argument(
        '--dev-name-prefix',
        type=str,
        default=None,
        help="Device name prefix to match"
    )
    parser.add_argument(
        '--scan-duration',
        type=str,
        default="5",
        help="Duration of the device scan (default: 5 seconds)"
    )
    parser.add_argument(
        '--log-file',
        type=str,
        default=None,
        help="Optional log file path to save all output (appends to existing file)"
    )
    parser.add_argument(
        '--text-font-size',
        type=str,
        default="10",
        help="Font size used for the text output (default: 10 points)"
    )
    args = parser.parse_args()
    
    root = tk.Tk()
    #root.option_add('*Font', 'System 10')
    app = BLEScanner(root, cmdArgs=args)
    
    # Disconnect (if needed) and close log file on exit
    def onClosing():
        # Disconnect from BLE device if connected
        if app.client and app.client.is_connected:
            app.log("\nDisconnecting before exit...")
            if app.loop and app.loop.is_running():
                # Schedule disconnect in the event loop
                future = asyncio.run_coroutine_threadsafe(app.async_disconnect(), app.loop)
                try:
                    future.result(timeout=3.0)  # Wait up to 3 seconds for disconnect
                except Exception as e:
                    print(f"Error during disconnect: {e}")
        
        # Close log file      
        if app.logFileHandle:
            app._write_to_log_file(f"\n{'='*80}\n")
            app._write_to_log_file(f"Session ended at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            app._write_to_log_file(f"{'='*80}\n\n")
            app.logFileHandle.close()
            
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", onClosing)  
    root.mainloop()

if __name__ == "__main__":
    main()

