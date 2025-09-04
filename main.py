#!/usr/bin/env python3
"""
URBARN Android Light Controller
==============================

Mobile Android app for controlling URBARN Bluetooth mesh lights.
Built with Kivy and using reverse-engineered credentials.

Author: Reverse Engineering Analysis
Date: 2025-01-04
"""

import asyncio
from threading import Thread
import logging
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.clock import Clock, mainthread
from kivy.logger import Logger
import time

# Import our mesh controller
try:
    from urbarn_mesh_controller import UrbanMeshController
except ImportError:
    Logger.error("URBARN: Failed to import UrbanMeshController")
    UrbanMeshController = None

# Configure logging for Android
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UrbanApp(App):
    """
    Main Android app for URBARN light control
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if UrbanMeshController is None:
            raise Exception("UrbanMeshController not available")
        self.controller = UrbanMeshController()
        self.discovered_devices = []
        self.connected_devices = {}
        self.loop = None
        self.loop_thread = None
        
        # UI references
        self.status_label = None
        self.device_layout = None
        self.scan_button = None
        self.main_layout = None
        
    def build(self):
        """
        Build the main UI
        """
        self.title = "URBARN Light Controller"
        
        # Main layout
        self.main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Title
        title = Label(
            text='🚀 URBARN Light Controller',
            size_hint_y=None,
            height='48dp',
            font_size='20sp',
            bold=True
        )
        self.main_layout.add_widget(title)
        
        # Status label
        self.status_label = Label(
            text='Ready to scan for URBARN devices...',
            size_hint_y=None,
            height='40dp',
            text_size=(None, None)
        )
        self.main_layout.add_widget(self.status_label)
        
        # Control buttons
        button_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='50dp', spacing=10)
        
        self.scan_button = Button(
            text='🔍 Scan for Devices',
            size_hint_x=0.5
        )
        self.scan_button.bind(on_press=self.on_scan_pressed)
        button_layout.add_widget(self.scan_button)
        
        refresh_button = Button(
            text='🔄 Refresh',
            size_hint_x=0.25
        )
        refresh_button.bind(on_press=self.on_refresh_pressed)
        button_layout.add_widget(refresh_button)
        
        about_button = Button(
            text='ℹ️ About',
            size_hint_x=0.25
        )
        about_button.bind(on_press=self.show_about)
        button_layout.add_widget(about_button)
        
        self.main_layout.add_widget(button_layout)
        
        # Scrollable device list
        scroll = ScrollView()
        self.device_layout = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.device_layout.bind(minimum_height=self.device_layout.setter('height'))
        scroll.add_widget(self.device_layout)
        
        self.main_layout.add_widget(scroll)
        
        # Start asyncio loop in background thread
        self.start_async_loop()
        
        return self.main_layout
    
    def start_async_loop(self):
        """
        Start asyncio event loop in background thread
        """
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
            
        self.loop_thread = Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
        
        # Wait for loop to be ready
        while self.loop is None:
            time.sleep(0.01)
    
    @mainthread
    def update_status(self, message):
        """
        Update status label on main thread
        """
        if self.status_label:
            self.status_label.text = message
            Logger.info(f"URBARN: {message}")
    
    def on_scan_pressed(self, button):
        """
        Handle scan button press
        """
        if self.loop and not self.loop.is_closed():
            # Disable button during scan
            button.disabled = True
            button.text = "🔍 Scanning..."
            
            # Run scan in async loop
            asyncio.run_coroutine_threadsafe(
                self.scan_for_devices_async(button), 
                self.loop
            )
    
    async def scan_for_devices_async(self, button):
        """
        Async method to scan for devices
        """
        try:
            self.update_status("🔍 Scanning for URBARN devices...")
            
            # Clear previous devices
            self.discovered_devices = []
            Clock.schedule_once(lambda dt: self.clear_device_list(), 0)
            
            # Scan for devices
            devices = await self.controller.scan_for_urbarn_devices(scan_time=10)
            
            if devices:
                self.discovered_devices = devices
                self.update_status(f"✅ Found {len(devices)} URBARN devices")
                
                # Add devices to UI
                Clock.schedule_once(lambda dt: self.populate_device_list(), 0)
                
            else:
                self.update_status("❌ No URBARN devices found. Make sure lights are on and nearby.")
                
        except Exception as e:
            self.update_status(f"❌ Scan error: {str(e)}")
            Logger.error(f"URBARN: Scan error: {e}")
        
        finally:
            # Re-enable button
            Clock.schedule_once(lambda dt: self.reset_scan_button(button), 0)
    
    @mainthread
    def reset_scan_button(self, button):
        """
        Reset scan button state
        """
        button.disabled = False
        button.text = "🔍 Scan for Devices"
    
    @mainthread
    def clear_device_list(self):
        """
        Clear device list UI
        """
        self.device_layout.clear_widgets()
    
    @mainthread  
    def populate_device_list(self):
        """
        Populate device list in UI
        """
        self.device_layout.clear_widgets()
        
        for device in self.discovered_devices:
            device_widget = self.create_device_widget(device)
            self.device_layout.add_widget(device_widget)
    
    def create_device_widget(self, device):
        """
        Create a widget for a discovered device
        """
        layout = BoxLayout(orientation='horizontal', size_hint_y=None, height='80dp', spacing=5)
        
        # Device info
        info_layout = BoxLayout(orientation='vertical', size_hint_x=0.6)
        
        name_label = Label(
            text=f"📡 {device.name or 'Unknown'}",
            size_hint_y=None,
            height='30dp',
            text_size=(None, None),
            font_size='14sp',
            bold=True
        )
        info_layout.add_widget(name_label)
        
        addr_label = Label(
            text=f"📍 {device.address}",
            size_hint_y=None, 
            height='25dp',
            text_size=(None, None),
            font_size='11sp'
        )
        info_layout.add_widget(addr_label)
        
        layout.add_widget(info_layout)
        
        # Control buttons
        button_layout = BoxLayout(orientation='horizontal', size_hint_x=0.4, spacing=3)
        
        connect_btn = Button(
            text='🔗 Connect',
            size_hint_x=0.5,
            font_size='11sp'
        )
        connect_btn.bind(on_press=lambda x: self.connect_device(device))
        button_layout.add_widget(connect_btn)
        
        control_btn = Button(
            text='💡 Control',
            size_hint_x=0.5,
            font_size='11sp'
        )
        control_btn.bind(on_press=lambda x: self.show_device_controls(device))
        button_layout.add_widget(control_btn)
        
        layout.add_widget(button_layout)
        
        return layout
    
    def connect_device(self, device):
        """
        Connect to a specific device
        """
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self.connect_device_async(device),
                self.loop
            )
    
    async def connect_device_async(self, device):
        """
        Async method to connect to device
        """
        try:
            self.update_status(f"🔗 Connecting to {device.name or device.address}...")
            
            # Connect to device
            success = await self.controller.connect_to_device(device)
            
            if success:
                # Authenticate
                self.update_status("🔐 Authenticating...")
                auth_success = await self.controller.authenticate_with_mesh(device.address)
                
                if auth_success:
                    self.connected_devices[device.address] = device
                    self.update_status(f"✅ Connected and authenticated with {device.name or device.address}")
                else:
                    self.update_status(f"❌ Authentication failed for {device.name or device.address}")
            else:
                self.update_status(f"❌ Failed to connect to {device.name or device.address}")
                
        except Exception as e:
            self.update_status(f"❌ Connection error: {str(e)}")
            Logger.error(f"URBARN: Connection error: {e}")
    
    def show_device_controls(self, device):
        """
        Show control popup for device
        """
        if device.address not in self.connected_devices:
            self.show_popup("Device Not Connected", "Please connect to this device first.")
            return
        
        # Create control popup
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        title = Label(
            text=f"Control {device.name or device.address}",
            size_hint_y=None,
            height='40dp',
            font_size='16sp',
            bold=True
        )
        content.add_widget(title)
        
        # Light control buttons
        button_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height='50dp')
        
        on_btn = Button(text='💡 Turn ON', size_hint_x=0.5)
        on_btn.bind(on_press=lambda x: self.control_light(device, True))
        button_layout.add_widget(on_btn)
        
        off_btn = Button(text='⚫ Turn OFF', size_hint_x=0.5)
        off_btn.bind(on_press=lambda x: self.control_light(device, False))
        button_layout.add_widget(off_btn)
        
        content.add_widget(button_layout)
        
        # Close button
        close_btn = Button(text='Close', size_hint_y=None, height='40dp')
        content.add_widget(close_btn)
        
        popup = Popup(
            title="Device Controls",
            content=content,
            size_hint=(0.8, 0.6)
        )
        
        close_btn.bind(on_press=popup.dismiss)
        popup.open()
    
    def control_light(self, device, turn_on):
        """
        Control light on/off
        """
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self.control_light_async(device, turn_on),
                self.loop
            )
    
    async def control_light_async(self, device, turn_on):
        """
        Async method to control light
        """
        try:
            action = "ON" if turn_on else "OFF"
            self.update_status(f"💡 Turning {action} {device.name or device.address}...")
            
            if turn_on:
                success = await self.controller.turn_on_light(device.address)
            else:
                success = await self.controller.turn_off_light(device.address)
            
            if success:
                self.update_status(f"✅ Successfully turned {action} {device.name or device.address}")
            else:
                self.update_status(f"❌ Failed to turn {action} {device.name or device.address}")
                
        except Exception as e:
            self.update_status(f"❌ Control error: {str(e)}")
            Logger.error(f"URBARN: Control error: {e}")
    
    def on_refresh_pressed(self, button):
        """
        Handle refresh button
        """
        self.update_status("🔄 Refreshing...")
        Clock.schedule_once(lambda dt: self.clear_device_list(), 0)
        self.discovered_devices = []
        self.connected_devices = {}
        self.update_status("Ready to scan for URBARN devices...")
    
    def show_about(self, button):
        """
        Show about popup
        """
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        about_text = """
🚀 URBARN Light Controller

Custom Android app for controlling URBARN Bluetooth mesh lights using reverse-engineered credentials.

🔐 Discovered Mesh Credentials:
• Primary: URBARN / 15102
• Secondary: Fulife / 2846

✨ Features:
• Scan for nearby URBARN devices
• Connect and authenticate automatically
• Control lights (ON/OFF)
• No official app required!

🛠️ Built with:
• Python + Kivy
• Bleak Bluetooth library
• Reverse engineering analysis

Author: Custom Development
Date: 2025-01-04
"""
        
        about_label = Label(
            text=about_text,
            text_size=(None, None),
            valign='top'
        )
        content.add_widget(about_label)
        
        close_btn = Button(text='Close', size_hint_y=None, height='40dp')
        content.add_widget(close_btn)
        
        popup = Popup(
            title="About URBARN Controller",
            content=content,
            size_hint=(0.9, 0.8)
        )
        
        close_btn.bind(on_press=popup.dismiss)
        popup.open()
    
    def show_popup(self, title, message):
        """
        Show a simple popup message
        """
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        label = Label(text=message)
        content.add_widget(label)
        
        close_btn = Button(text='Close', size_hint_y=None, height='40dp')
        content.add_widget(close_btn)
        
        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.7, 0.4)
        )
        
        close_btn.bind(on_press=popup.dismiss)
        popup.open()
    
    def on_stop(self):
        """
        Clean up when app is closed
        """
        if self.loop and not self.loop.is_closed():
            # Disconnect all devices
            asyncio.run_coroutine_threadsafe(
                self.controller.disconnect_all(),
                self.loop
            )
            
            # Stop the loop
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        return True

if __name__ == '__main__':
    UrbanApp().run()
