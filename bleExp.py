import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import asyncio
import threading
from bleak import BleakScanner, BleakClient
from typing import Optional

class BLEScanner:
    def __init__(self, root):
        self.root = root
        self.root.title("BLE Device Scanner")
        self.root.geometry("1000x1200")
        
        self.client: Optional[BleakClient] = None
        self.scanning = False
        self.writable_chars = {}  # Store writable characteristics
        self.notifiable_chars = {}  # Store notifiable/indicatable characteristics
        self.active_notifications = {}  # Track active notifications
        self.loop = None  # Store the event loop
        self.discovered_devices = []  # Store discovered devices
        self.device_adv_data = {}  # Store advertisement data
        
        # Create UI
        self.create_widgets()
        
    def create_widgets(self):
        # Top frame for UUID input and scan button
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="Service UUID:").pack(side=tk.LEFT, padx=5)
        self.uuid_entry = ttk.Entry(top_frame, width=20)
        self.uuid_entry.insert(0, "180D")  # Default: Heart Rate Service
        self.uuid_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(top_frame, text="Scan Duration (sec):").pack(side=tk.LEFT, padx=(20, 5))
        self.scan_duration_entry = ttk.Entry(top_frame, width=8)
        self.scan_duration_entry.insert(0, "5")
        self.scan_duration_entry.pack(side=tk.LEFT, padx=5)
        
        self.scan_btn = ttk.Button(top_frame, text="Start Scan", command=self.toggle_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=5)
        
        self.status_label = ttk.Label(top_frame, text="Ready", foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        # Separator
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # Device list frame
        device_frame = ttk.LabelFrame(self.root, text="Discovered Devices", padding="10")
        device_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)
        
        # Create listbox with scrollbar
        list_container = ttk.Frame(device_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL)
        self.device_listbox = tk.Listbox(
            list_container,
            height=6,
            font=("Consolas", 9),
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.device_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.device_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Connect button for selected device
        button_frame = ttk.Frame(device_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.connect_btn = ttk.Button(
            button_frame,
            text="Connect to Selected Device",
            command=self.connect_to_selected,
            state=tk.DISABLED
        )
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        self.show_adv_btn = ttk.Button(
            button_frame,
            text="Show Advertisement Data",
            command=self.show_advertisement_data,
            state=tk.DISABLED
        )
        self.show_adv_btn.pack(side=tk.LEFT, padx=5)
        
        # Separator
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # Main output area
        output_frame = ttk.Frame(self.root, padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(output_frame, text="Device Information:").pack(anchor=tk.W)
        
        self.output_text = scrolledtext.ScrolledText(
            output_frame, 
            wrap=tk.WORD, 
            width=100, 
            height=20,
            font=("Consolas", 9)
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Bottom frame for disconnect button
        bottom_frame = ttk.Frame(self.root, padding="10")
        bottom_frame.pack(fill=tk.X)
        
        self.disconnect_btn = ttk.Button(
            bottom_frame, 
            text="Disconnect", 
            command=self.disconnect_device,
            state=tk.DISABLED
        )
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        # Write characteristic frame
        write_frame = ttk.LabelFrame(self.root, text="Write to Characteristic", padding="10")
        write_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Characteristic UUID
        ttk.Label(write_frame, text="Char UUID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.write_uuid_entry = ttk.Entry(write_frame, width=40)
        self.write_uuid_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Value type selection
        ttk.Label(write_frame, text="Value Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        type_frame = ttk.Frame(write_frame)
        type_frame.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        self.value_type = tk.StringVar(value="hex")
        ttk.Radiobutton(type_frame, text="Hex", variable=self.value_type, value="hex").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Decimal", variable=self.value_type, value="dec").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="UTF-8 String", variable=self.value_type, value="string").pack(side=tk.LEFT, padx=5)
        
        # Value input
        ttk.Label(write_frame, text="Value:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.write_value_entry = ttk.Entry(write_frame, width=40)
        self.write_value_entry.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Write button
        self.write_btn = ttk.Button(
            write_frame, 
            text="Write Value", 
            command=self.write_characteristic,
            state=tk.DISABLED
        )
        self.write_btn.grid(row=3, column=1, sticky=tk.E, padx=5, pady=5)
        
        # Configure grid weights
        write_frame.columnconfigure(1, weight=1)
        
        # Notification/Indication frame
        notify_frame = ttk.LabelFrame(self.root, text="Notifications/Indications", padding="10")
        notify_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Characteristic UUID for notifications
        ttk.Label(notify_frame, text="Char UUID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.notify_uuid_entry = ttk.Entry(notify_frame, width=40)
        self.notify_uuid_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Notification buttons
        button_frame = ttk.Frame(notify_frame)
        button_frame.grid(row=1, column=1, sticky=tk.E, padx=5, pady=5)
        
        self.notify_enable_btn = ttk.Button(
            button_frame, 
            text="Enable Notifications", 
            command=self.enable_notifications,
            state=tk.DISABLED
        )
        self.notify_enable_btn.pack(side=tk.LEFT, padx=5)
        
        self.notify_disable_btn = ttk.Button(
            button_frame, 
            text="Disable Notifications", 
            command=self.disable_notifications,
            state=tk.DISABLED
        )
        self.notify_disable_btn.pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        notify_frame.columnconfigure(1, weight=1)
        
    def log(self, message):
        """Thread-safe logging to the text widget"""
        self.root.after(0, self._log_impl, message)
        
    def _log_impl(self, message):
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        
    def update_status(self, message, color="blue"):
        """Update status label"""
        self.root.after(0, lambda: self.status_label.config(text=message, foreground=color))
        
    def _enable_write_button(self):
        """Enable the write button (must be called from main thread)"""
        self.write_btn.config(state=tk.NORMAL)
        
    def _enable_notify_buttons(self):
        """Enable the notification buttons (must be called from main thread)"""
        self.notify_enable_btn.config(state=tk.NORMAL)
        self.notify_disable_btn.config(state=tk.NORMAL)
        
    def toggle_scan(self):
        if not self.scanning:
            self.start_scan()
        else:
            self.stop_scan()
            
    def start_scan(self):
        uuid_input = self.uuid_entry.get().strip().replace("-", "").replace(" ", "")
        if not uuid_input:
            messagebox.showerror("Error", "Please enter a UUID")
            return
            
        # Validate hex input
        try:
            int(uuid_input, 16)
        except ValueError:
            messagebox.showerror("Error", "Invalid hex UUID")
            return
        
        # Determine if it's a 16-bit or 128-bit UUID
        if len(uuid_input) == 4:
            # 16-bit UUID
            uuid_type = "16-bit"
        elif len(uuid_input) == 32:
            # 128-bit UUID (without dashes)
            uuid_type = "128-bit"
        else:
            messagebox.showerror("Error", "UUID must be 4 hex digits (16-bit) or 32 hex digits (128-bit)")
            return
        
        # Validate scan duration
        try:
            duration = float(self.scan_duration_entry.get().strip())
            if duration <= 0:
                messagebox.showerror("Error", "Scan duration must be positive")
                return
        except ValueError:
            messagebox.showerror("Error", "Invalid scan duration")
            return
            
        self.scanning = True
        self.scan_btn.config(text="Stop Scan")
        self.uuid_entry.config(state=tk.DISABLED)
        self.scan_duration_entry.config(state=tk.DISABLED)
        self.output_text.delete(1.0, tk.END)
        
        # Run scan in separate thread
        thread = threading.Thread(target=self.run_scan, args=(uuid_input, uuid_type, duration), daemon=True)
        thread.start()
        
    def stop_scan(self):
        self.scanning = False
        self.scan_btn.config(text="Start Scan")
        self.uuid_entry.config(state=tk.NORMAL)
        self.scan_duration_entry.config(state=tk.NORMAL)
        self.update_status("Scan stopped", "orange")
        
    def run_scan(self, uuid_input, uuid_type, duration):
        """Run the BLE scan in an asyncio event loop"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.scan_for_devices(uuid_input, uuid_type, duration))
        except Exception as e:
            self.log(f"Error: {str(e)}")
            self.update_status(f"Error: {str(e)}", "red")
        finally:
            self.loop.close()
            self.loop = None
            
    async def scan_for_devices(self, uuid_input, uuid_type, duration):
        """Scan for BLE devices with the specified UUID"""
        # Convert to full 128-bit UUID if needed
        if uuid_type == "16-bit":
            full_uuid = f"0000{uuid_input.lower()}-0000-1000-8000-00805f9b34fb"
        else:
            # Format 128-bit UUID with dashes
            uuid_lower = uuid_input.lower()
            full_uuid = f"{uuid_lower[0:8]}-{uuid_lower[8:12]}-{uuid_lower[12:16]}-{uuid_lower[16:20]}-{uuid_lower[20:32]}"
        
        self.log(f"Scanning for devices advertising UUID: {uuid_input}")
        self.log(f"UUID Type: {uuid_type}")
        self.log(f"Full UUID: {full_uuid}")
        self.log(f"Scan duration: {duration} seconds")
        self.log("-" * 80)
        self.update_status("Scanning...", "green")
        
        matching_devices = []
        device_adv_data = {}  # Store advertisement data for each device
        
        def detection_callback(device, advertisement_data):
            """Called when a device is detected"""
            # Check if the UUID is in the advertised service UUIDs
            if advertisement_data.service_uuids:
                adv_uuids = [u.lower() for u in advertisement_data.service_uuids]
                if full_uuid in adv_uuids:
                    # Avoid duplicates
                    if not any(d.address == device.address for d in matching_devices):
                        matching_devices.append(device)
                        device_adv_data[device.address] = advertisement_data
                        self.log(f"Found: {device.name or 'Unknown'} ({device.address})")
        
        try:
            # Create scanner with callback
            scanner = BleakScanner(detection_callback=detection_callback)
            
            # Start scanning
            await scanner.start()
            await asyncio.sleep(duration)
            await scanner.stop()
            
            if not self.scanning:
                return
            
            if not matching_devices:
                self.log(f"\nNo devices found advertising UUID {uuid_input}")
                self.log("Note: The device must be actively advertising this service UUID")
                self.update_status("No matching devices found", "orange")
                self.scanning = False
                self.root.after(0, lambda: self.scan_btn.config(text="Start Scan"))
                self.root.after(0, lambda: self.uuid_entry.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.scan_duration_entry.config(state=tk.NORMAL))
                return
            
            # Store discovered devices
            self.discovered_devices = matching_devices
            
            self.log(f"\nFound {len(matching_devices)} device(s) with UUID {uuid_input}\n")
            
            # Populate device list
            self.root.after(0, self._populate_device_list)
            self.update_status(f"Found {len(matching_devices)} device(s) - Select one to connect", "blue")
            
        except Exception as e:
            self.log(f"\nScan error: {str(e)}")
            self.update_status(f"Error: {str(e)}", "red")
        finally:
            self.scanning = False
            self.root.after(0, lambda: self.scan_btn.config(text="Start Scan"))
            self.root.after(0, lambda: self.uuid_entry.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.scan_duration_entry.config(state=tk.NORMAL))
            
    def _populate_device_list(self):
        """Populate the device listbox (must be called from main thread)"""
        self.device_listbox.delete(0, tk.END)
        for device in self.discovered_devices:
            display_name = f"{device.name or 'Unknown':30s} [{device.address}]"
            self.device_listbox.insert(tk.END, display_name)
        
        if self.discovered_devices:
            self.connect_btn.config(state=tk.NORMAL)
            self.show_adv_btn.config(state=tk.NORMAL)
            self.device_listbox.selection_set(0)  # Select first device by default
            
    def connect_to_selected(self):
        """Connect to the device selected in the listbox"""
        selection = self.device_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a device from the list")
            return
        
        device_index = selection[0]
        device = self.discovered_devices[device_index]
        
        self.output_text.delete(1.0, tk.END)
        self.log(f"Connecting to: {device.name or 'Unknown'} ({device.address})")
        self.update_status(f"Connecting to {device.address}...", "green")
        
        # Disable buttons during connection
        self.connect_btn.config(state=tk.DISABLED)
        self.show_adv_btn.config(state=tk.DISABLED)
        
        # Run connection in separate thread
        thread = threading.Thread(target=self.run_connect, args=(device,), daemon=True)
        thread.start()
        
    def run_connect(self, device):
        """Run the connection in an asyncio event loop"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.connect_and_explore(device))
        except Exception as e:
            self.log(f"Connection error: {str(e)}")
            self.update_status(f"Error: {str(e)}", "red")
        finally:
            self.loop.close()
            self.loop = None
            
    def show_advertisement_data(self):
        """Show detailed advertisement data for selected device"""
        selection = self.device_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a device from the list")
            return
        
        device_index = selection[0]
        device = self.discovered_devices[device_index]
        adv_data = self.device_adv_data.get(device.address)
        
        self.output_text.delete(1.0, tk.END)
        
        if adv_data:
            self.log(f"{'=' * 80}")
            self.log(f"Device: {device.name or 'Unknown'}")
            self.log(f"Address: {device.address}")
            self.log(f"\nAdvertisement Data:")
            
            # Local name
            if adv_data.local_name:
                self.log(f"    Local Name: {adv_data.local_name}")
            
            # RSSI
            if adv_data.rssi is not None:
                self.log(f"    RSSI: {adv_data.rssi} dBm")
            
            # TX Power
            if adv_data.tx_power is not None:
                self.log(f"    TX Power: {adv_data.tx_power} dBm")
            
            # Service UUIDs
            if adv_data.service_uuids:
                self.log(f"    Service UUIDs ({len(adv_data.service_uuids)}):")
                for uuid in adv_data.service_uuids:
                    self.log(f"        - {uuid}")
            
            # Service Data
            if adv_data.service_data:
                self.log(f"    Service Data ({len(adv_data.service_data)} entries):")
                for uuid, data in adv_data.service_data.items():
                    hex_data = " ".join(f"{b:02x}" for b in data)
                    self.log(f"        {uuid}: {hex_data}")
            
            # Manufacturer Data
            if adv_data.manufacturer_data:
                self.log(f"    Manufacturer Data ({len(adv_data.manufacturer_data)} entries):")
                for company_id, data in adv_data.manufacturer_data.items():
                    hex_data = " ".join(f"{b:02x}" for b in data)
                    self.log(f"        Company ID 0x{company_id:04x}: {hex_data}")
            
            # Platform specific data
            if hasattr(adv_data, 'platform_data'):
                platform_data = adv_data.platform_data
                
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
            
            self.root.after(0, lambda: self.disconnect_btn.config(state=tk.NORMAL))
            
            if not self.client.is_connected:
                self.log("Failed to connect")
                return
                
            self.log("Connected successfully!\n")
            self.update_status("Connected - Reading services...", "green")
            
            # Get all services
            services = self.client.services
            service_list = list(services)
            # Sort services by UUID
            service_list.sort(key=lambda s: s.uuid)
            self.log(f"Device has {len(service_list)} service(s):\n")
            self.log("=" * 80)
            
            self.writable_chars.clear()
            self.notifiable_chars.clear()
            
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
                    
                    # Store writable characteristics
                    if "write" in char.properties or "write-without-response" in char.properties:
                        self.writable_chars[char.uuid] = char
                    
                    # Store notifiable/indicatable characteristics
                    if "notify" in char.properties or "indicate" in char.properties:
                        self.notifiable_chars[char.uuid] = char
                    
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
                    if char.descriptors:
                        self.log(f"        Descriptors: {len(char.descriptors)}")
                        for desc in char.descriptors:
                            self.log(f"            - {desc.uuid}")
                            
            self.log("\n" + "=" * 80)
            self.log("\nExploration complete!")
            
            if self.writable_chars:
                self.log(f"\nFound {len(self.writable_chars)} writable characteristic(s)")
                self.root.after(0, self._enable_write_button)
            
            if self.notifiable_chars:
                self.log(f"Found {len(self.notifiable_chars)} notifiable/indicatable characteristic(s)")
                self.root.after(0, self._enable_notify_buttons)
            
            self.update_status("Connected and ready", "blue")
            
            # Keep the loop running for write operations
            while self.client and self.client.is_connected:
                await asyncio.sleep(0.1)
            
        except Exception as e:
            self.log(f"\nConnection error: {str(e)}")
            self.update_status(f"Error: {str(e)}", "red")
            if self.client and self.client.is_connected:
                await self.client.disconnect()
            self.client = None
            self.writable_chars.clear()
            self.notifiable_chars.clear()
            self.active_notifications.clear()
            self.root.after(0, lambda: self.disconnect_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.write_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.notify_enable_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.notify_disable_btn.config(state=tk.DISABLED))
            
    def disconnect_device(self):
        """Disconnect from the current device"""
        if self.client:
            thread = threading.Thread(target=self.run_disconnect, daemon=True)
            thread.start()
            
    def run_disconnect(self):
        """Run disconnect in asyncio loop"""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.async_disconnect(), self.loop)
        else:
            # Fallback if loop is not available
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.async_disconnect())
            finally:
                loop.close()
            
    async def async_disconnect(self):
        """Disconnect from device"""
        try:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
                self.log("\nDisconnected")
        except Exception as e:
            self.log(f"\nDisconnect error: {str(e)}")
        finally:
            self.client = None
            self.writable_chars.clear()
            self.notifiable_chars.clear()
            self.active_notifications.clear()
            self.update_status("Disconnected", "orange")
            self.root.after(0, lambda: self.disconnect_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.write_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.notify_enable_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.notify_disable_btn.config(state=tk.DISABLED))
            
    def write_characteristic(self):
        """Write a value to a characteristic"""
        if not self.client:
            messagebox.showerror("Error", "Not connected to a device")
            return
            
        uuid = self.write_uuid_entry.get().strip()
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
            if uuid_normalized not in self.writable_chars:
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
            self.update_status("Writing...", "green")
            
            await self.client.write_gatt_char(uuid_normalized, data)
            
            self.log("Write successful!")
            self.update_status("Write complete", "blue")
            
        except Exception as e:
            self.log(f"\nWrite failed: {str(e)}")
            self.update_status(f"Write failed: {str(e)}", "red")
            
    def enable_notifications(self):
        """Enable notifications/indications for a characteristic"""
        if not self.client:
            messagebox.showerror("Error", "Not connected to a device")
            return
            
        uuid = self.notify_uuid_entry.get().strip()
        if not uuid:
            messagebox.showerror("Error", "Please enter a characteristic UUID")
            return
        
        # Schedule the enable operation in the same event loop
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.start_notify(uuid),
                self.loop
            )
        else:
            messagebox.showerror("Error", "Event loop not available")
            
    def disable_notifications(self):
        """Disable notifications/indications for a characteristic"""
        if not self.client:
            messagebox.showerror("Error", "Not connected to a device")
            return
            
        uuid = self.notify_uuid_entry.get().strip()
        if not uuid:
            messagebox.showerror("Error", "Please enter a characteristic UUID")
            return
        
        # Schedule the disable operation in the same event loop
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.stop_notify(uuid),
                self.loop
            )
        else:
            messagebox.showerror("Error", "Event loop not available")
            
    async def start_notify(self, uuid):
        """Start notifications/indications for a characteristic"""
        try:
            # Normalize UUID
            uuid_normalized = self.normalize_uuid(uuid)
            
            # Check if this characteristic supports notifications/indications
            if uuid_normalized not in self.notifiable_chars:
                self.log(f"\nError: Characteristic {uuid} does not support notifications/indications")
                return
            
            # Check if already subscribed
            if uuid_normalized in self.active_notifications:
                self.log(f"\nNotifications already enabled for {uuid}")
                return
            
            # Define notification callback
            def notification_handler(sender, data):
                hex_value = " ".join(f"{b:02x}" for b in data)
                timestamp = asyncio.get_event_loop().time()
                self.log(f"[NOTIFY] {uuid}: {hex_value}")
                # Try to decode as string
                try:
                    str_value = data.decode('utf-8', errors='ignore')
                    if str_value.isprintable():
                        self.log(f"         String: {str_value}")
                except:
                    pass
            
            # Start notifications
            self.log(f"\nEnabling notifications for {uuid}...")
            await self.client.start_notify(uuid_normalized, notification_handler)
            self.active_notifications[uuid_normalized] = True
            self.log("Notifications enabled!")
            self.update_status("Notifications enabled", "blue")
            
        except Exception as e:
            self.log(f"\nFailed to enable notifications: {str(e)}")
            self.update_status(f"Notification error: {str(e)}", "red")
            
    async def stop_notify(self, uuid):
        """Stop notifications/indications for a characteristic"""
        try:
            # Normalize UUID
            uuid_normalized = self.normalize_uuid(uuid)
            
            # Check if notifications are active
            if uuid_normalized not in self.active_notifications:
                self.log(f"\nNo active notifications for {uuid}")
                return
            
            # Stop notifications
            self.log(f"\nDisabling notifications for {uuid}...")
            await self.client.stop_notify(uuid_normalized)
            del self.active_notifications[uuid_normalized]
            self.log("Notifications disabled!")
            self.update_status("Notifications disabled", "blue")
            
        except Exception as e:
            self.log(f"\nFailed to disable notifications: {str(e)}")
            self.update_status(f"Notification error: {str(e)}", "red")
            
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
    root = tk.Tk()
    app = BLEScanner(root)
    root.mainloop()

if __name__ == "__main__":
    main()

