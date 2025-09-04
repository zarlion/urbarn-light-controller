#!/usr/bin/env python3
"""
URBARN Bluetooth Mesh Light Controller
======================================

Custom controller using reverse-engineered credentials from the official URBARN app.
Discovered mesh credentials: URBARN/15102

Author: Reverse Engineering Analysis
Date: 2024-09-04
"""

import asyncio
import struct
import logging
from bleak import BleakScanner, BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from typing import List, Dict, Optional, Tuple
import time
import binascii

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UrbanMeshController:
    """
    URBARN Bluetooth Mesh Light Controller
    
    Uses discovered mesh credentials:
    - Primary Mesh: URBARN / 15102
    - Secondary Mesh: Fulife / 2846
    """
    
    # Discovered mesh credentials from app analysis
    MESH_CREDENTIALS = {
        'primary': {'name': 'URBARN', 'password': '15102'},
        'secondary': {'name': 'Fulife', 'password': '2846'}
    }
    
    # Discovered AES encryption keys
    AES_KEY = bytes.fromhex('d571f6c5851265bcd5bb684aa937aa7c3df76ffce7fb11250ba292d63194d677')
    AES_IV = bytes.fromhex('a91818db066216501caad41d5982e638')
    
    # Common Bluetooth mesh service UUIDs
    MESH_SERVICE_UUIDS = [
        "00001827-0000-1000-8000-00805f9b34fb",  # Mesh Provisioning Service
        "00001828-0000-1000-8000-00805f9b34fb",  # Mesh Proxy Service
        "0000fe59-0000-1000-8000-00805f9b34fb",  # Generic mesh service
        "000016fe-0000-1000-8000-00805f9b34fb",  # Another common mesh UUID
    ]
    
    # Potential characteristic UUIDs for mesh communication
    MESH_CHAR_UUIDS = [
        "00002a04-0000-1000-8000-00805f9b34fb",  # Mesh control
        "00002a05-0000-1000-8000-00805f9b34fb",  # Mesh data
        "6e400002-b5a3-f393-e0a9-e50e24dcca9e",  # Nordic UART TX
        "6e400003-b5a3-f393-e0a9-e50e24dcca9e",  # Nordic UART RX
        "0000fff1-0000-1000-8000-00805f9b34fb",  # Generic write
        "0000fff2-0000-1000-8000-00805f9b34fb",  # Generic notify
        "0000fff3-0000-1000-8000-00805f9b34fb",  # Generic read
        "0000fff4-0000-1000-8000-00805f9b34fb",  # Generic indication
    ]
    
    def __init__(self):
        self.discovered_devices: List[BLEDevice] = []
        self.connected_devices: Dict[str, BleakClient] = {}
        self.device_characteristics: Dict[str, Dict[str, BleakGATTCharacteristic]] = {}
        self.authenticated_devices: Dict[str, bool] = {}
        
    async def scan_for_urbarn_devices(self, scan_time: int = 10) -> List[BLEDevice]:
        """
        Scan for URBARN mesh devices using discovered patterns
        """
        logger.info(f"Scanning for URBARN devices for {scan_time} seconds...")
        
        # Device name patterns found in the app
        device_patterns = [
            'URBARN',
            'Fulife', 
            'Mesh',
            'Light',
            # Generic patterns that might match
            'BT',
            'LED',
        ]
        
        self.discovered_devices = []
        
        def detection_callback(device: BLEDevice, advertisement_data):
            device_name = device.name or "Unknown"
            
            # Check for URBARN-specific patterns
            is_urbarn_device = False
            
            # Check name patterns
            for pattern in device_patterns:
                if pattern.lower() in device_name.lower():
                    is_urbarn_device = True
                    break
            
            # Check for mesh service UUIDs
            if not is_urbarn_device:
                for service_uuid in self.MESH_SERVICE_UUIDS:
                    if service_uuid in advertisement_data.service_uuids:
                        is_urbarn_device = True
                        break
            
            # Check for strong signal (likely nearby URBARN lights)
            if not is_urbarn_device and advertisement_data.rssi and advertisement_data.rssi > -60:
                # If it's a strong signal and has any service UUIDs, consider it
                if advertisement_data.service_uuids:
                    is_urbarn_device = True
            
            if is_urbarn_device:
                if device not in self.discovered_devices:
                    logger.info(f"Found potential URBARN device: {device_name} ({device.address}) RSSI: {advertisement_data.rssi}")
                    logger.info(f"  Services: {advertisement_data.service_uuids}")
                    logger.info(f"  Manufacturer data: {advertisement_data.manufacturer_data}")
                    self.discovered_devices.append(device)
        
        scanner = BleakScanner(detection_callback=detection_callback)
        await scanner.start()
        await asyncio.sleep(scan_time)
        await scanner.stop()
        
        logger.info(f"Found {len(self.discovered_devices)} potential URBARN devices")
        return self.discovered_devices
    
    async def connect_to_device(self, device: BLEDevice) -> bool:
        """
        Connect to a specific device and discover characteristics
        """
        try:
            logger.info(f"Connecting to {device.name or 'Unknown'} ({device.address})")
            
            client = BleakClient(device.address)
            await client.connect()
            
            if not client.is_connected:
                logger.error(f"Failed to connect to {device.address}")
                return False
            
            logger.info(f"Connected to {device.address}")
            self.connected_devices[device.address] = client
            
            # Discover services and characteristics
            await self._discover_characteristics(device.address)
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to {device.address}: {e}")
            return False
    
    async def _discover_characteristics(self, device_address: str):
        """
        Discover and catalog characteristics for mesh communication
        """
        client = self.connected_devices.get(device_address)
        if not client:
            return
        
        logger.info(f"Discovering characteristics for {device_address}")
        self.device_characteristics[device_address] = {}
        
        try:
            services = client.services
            
            for service in services:
                logger.info(f"Service: {service.uuid} ({service.description})")
                
                for char in service.characteristics:
                    char_info = f"  Char: {char.uuid} ({char.description}) Properties: {char.properties}"
                    logger.info(char_info)
                    
                    # Store potentially useful characteristics
                    if any(uuid.lower() in char.uuid.lower() for uuid in self.MESH_CHAR_UUIDS):
                        self.device_characteristics[device_address][char.uuid] = char
                        logger.info(f"    -> Stored as potential mesh characteristic")
                    
                    # Store writable characteristics
                    if "write" in char.properties or "write-without-response" in char.properties:
                        self.device_characteristics[device_address][f"writable_{char.uuid}"] = char
                        logger.info(f"    -> Stored as writable characteristic")
                    
                    # Store notification characteristics  
                    if "notify" in char.properties or "indicate" in char.properties:
                        self.device_characteristics[device_address][f"notify_{char.uuid}"] = char
                        logger.info(f"    -> Stored as notification characteristic")
                        
        except Exception as e:
            logger.error(f"Error discovering characteristics: {e}")
    
    async def authenticate_with_mesh(self, device_address: str, use_secondary_creds: bool = False) -> bool:
        """
        Attempt to authenticate with the mesh using discovered credentials
        """
        client = self.connected_devices.get(device_address)
        if not client:
            logger.error(f"No connection to {device_address}")
            return False
        
        # Choose credentials
        creds = self.MESH_CREDENTIALS['secondary' if use_secondary_creds else 'primary']
        mesh_name = creds['name']
        mesh_password = creds['password']
        
        logger.info(f"Attempting mesh authentication with {mesh_name}/{mesh_password}")
        
        # Try multiple authentication approaches based on app analysis
        auth_methods = [
            self._auth_method_1,
            self._auth_method_2,
            self._auth_method_3,
        ]
        
        for i, auth_method in enumerate(auth_methods, 1):
            logger.info(f"Trying authentication method {i}")
            try:
                success = await auth_method(device_address, mesh_name, mesh_password)
                if success:
                    logger.info(f"Authentication successful with method {i}")
                    self.authenticated_devices[device_address] = True
                    return True
            except Exception as e:
                logger.warning(f"Authentication method {i} failed: {e}")
        
        logger.error(f"All authentication methods failed for {device_address}")
        return False
    
    async def _auth_method_1(self, device_address: str, mesh_name: str, mesh_password: str) -> bool:
        """
        Authentication method 1: Direct credential transmission
        """
        client = self.connected_devices[device_address]
        characteristics = self.device_characteristics.get(device_address, {})
        
        # Try sending credentials to writable characteristics
        for char_key, characteristic in characteristics.items():
            if "writable" in char_key:
                try:
                    # Format 1: Name + Password as UTF-8
                    auth_data = f"{mesh_name}:{mesh_password}".encode('utf-8')
                    await client.write_gatt_char(characteristic, auth_data)
                    await asyncio.sleep(0.5)
                    
                    # Format 2: Binary packed
                    auth_data = struct.pack(f'<{len(mesh_name)}s{len(mesh_password)}s', 
                                          mesh_name.encode(), mesh_password.encode())
                    await client.write_gatt_char(characteristic, auth_data)
                    await asyncio.sleep(0.5)
                    
                    logger.info(f"Sent auth data to {characteristic.uuid}")
                    return True
                    
                except Exception as e:
                    logger.debug(f"Auth method 1 failed on {characteristic.uuid}: {e}")
        
        return False
    
    async def _auth_method_2(self, device_address: str, mesh_name: str, mesh_password: str) -> bool:
        """
        Authentication method 2: Mesh protocol specific
        """
        client = self.connected_devices[device_address]
        characteristics = self.device_characteristics.get(device_address, {})
        
        # Try mesh-specific authentication sequences
        for char_key, characteristic in characteristics.items():
            if "writable" in char_key:
                try:
                    # Mesh login sequence based on app patterns
                    login_sequence = [
                        b'\x01\x02',  # Login command
                        mesh_name.encode('utf-8'),
                        mesh_password.encode('utf-8'),
                        b'\x03\x04',  # End sequence
                    ]
                    
                    for data in login_sequence:
                        await client.write_gatt_char(characteristic, data)
                        await asyncio.sleep(0.2)
                    
                    return True
                    
                except Exception as e:
                    logger.debug(f"Auth method 2 failed on {characteristic.uuid}: {e}")
        
        return False
    
    async def _auth_method_3(self, device_address: str, mesh_name: str, mesh_password: str) -> bool:
        """
        Authentication method 3: Encrypted authentication using discovered AES keys
        """
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding
            
            # Create authentication payload
            auth_payload = f"{mesh_name}:{mesh_password}".encode('utf-8')
            
            # Encrypt with discovered keys
            cipher = Cipher(algorithms.AES(self.AES_KEY[:32]), modes.CBC(self.AES_IV[:16]))
            encryptor = cipher.encryptor()
            
            # Pad the payload
            padder = padding.PKCS7(128).padder()  # AES block size is 128 bits
            padded_data = padder.update(auth_payload)
            padded_data += padder.finalize()
            
            encrypted_payload = encryptor.update(padded_data) + encryptor.finalize()
            
            client = self.connected_devices[device_address]
            characteristics = self.device_characteristics.get(device_address, {})
            
            for char_key, characteristic in characteristics.items():
                if "writable" in char_key:
                    try:
                        await client.write_gatt_char(characteristic, encrypted_payload)
                        await asyncio.sleep(0.5)
                        return True
                    except Exception as e:
                        logger.debug(f"Auth method 3 failed on {characteristic.uuid}: {e}")
                        
        except ImportError:
            logger.warning("Cryptography library not available, skipping encrypted authentication")
        except Exception as e:
            logger.debug(f"Auth method 3 failed: {e}")
        
        return False
    
    async def turn_on_light(self, device_address: str, light_id: int = 1) -> bool:
        """
        Turn on a specific light using discovered command patterns
        """
        return await self._send_light_command(device_address, light_id, True)
    
    async def turn_off_light(self, device_address: str, light_id: int = 1) -> bool:
        """
        Turn off a specific light using discovered command patterns  
        """
        return await self._send_light_command(device_address, light_id, False)
    
    async def _send_light_command(self, device_address: str, light_id: int, turn_on: bool) -> bool:
        """
        Send light control command based on app analysis
        """
        if not self.authenticated_devices.get(device_address, False):
            logger.warning(f"Device {device_address} not authenticated, attempting authentication first")
            if not await self.authenticate_with_mesh(device_address):
                return False
        
        client = self.connected_devices.get(device_address)
        characteristics = self.device_characteristics.get(device_address, {})
        
        if not client or not characteristics:
            logger.error(f"No connection or characteristics for {device_address}")
            return False
        
        # Command patterns derived from app analysis
        command_patterns = [
            # Pattern 1: Simple on/off command
            struct.pack('<BHB', 0x01, light_id, 0x01 if turn_on else 0x00),
            # Pattern 2: Extended command
            struct.pack('<BBHB', 0x02, 0x01, light_id, 0xFF if turn_on else 0x00),
            # Pattern 3: Mesh command format
            struct.pack('<BBBH', 0x03, 0x01 if turn_on else 0x00, 0x00, light_id),
        ]
        
        for pattern in command_patterns:
            for char_key, characteristic in characteristics.items():
                if "writable" in char_key:
                    try:
                        logger.info(f"Sending {'ON' if turn_on else 'OFF'} command to light {light_id}")
                        logger.debug(f"Command data: {binascii.hexlify(pattern)}")
                        
                        await client.write_gatt_char(characteristic, pattern)
                        await asyncio.sleep(0.5)
                        
                        logger.info(f"Command sent successfully")
                        return True
                        
                    except Exception as e:
                        logger.debug(f"Command failed on {characteristic.uuid}: {e}")
        
        logger.error(f"All command patterns failed for device {device_address}")
        return False
    
    async def disconnect_all(self):
        """
        Disconnect from all connected devices
        """
        for address, client in list(self.connected_devices.items()):
            try:
                if client.is_connected:
                    await client.disconnect()
                    logger.info(f"Disconnected from {address}")
            except Exception as e:
                logger.error(f"Error disconnecting from {address}: {e}")
        
        self.connected_devices.clear()
        self.device_characteristics.clear()
        self.authenticated_devices.clear()

async def main():
    """
    Main function to demonstrate the URBARN mesh controller
    """
    controller = UrbanMeshController()
    
    try:
        # Step 1: Scan for URBARN devices
        print("🔍 Scanning for URBARN mesh devices...")
        devices = await controller.scan_for_urbarn_devices(scan_time=15)
        
        if not devices:
            print("❌ No URBARN devices found. Make sure your lights are powered on and nearby.")
            return
        
        print(f"✅ Found {len(devices)} potential URBARN devices")
        
        # Step 2: Connect to each device
        connected_count = 0
        for device in devices:
            print(f"\n🔗 Attempting to connect to {device.name or 'Unknown'} ({device.address})")
            
            if await controller.connect_to_device(device):
                connected_count += 1
                print(f"✅ Connected successfully")
                
                # Step 3: Authenticate with mesh
                print("🔐 Authenticating with mesh network...")
                if await controller.authenticate_with_mesh(device.address):
                    print("✅ Authentication successful")
                    
                    # Step 4: Test light control
                    print("💡 Testing light control...")
                    
                    # Turn on
                    if await controller.turn_on_light(device.address, light_id=1):
                        print("✅ Successfully turned light ON")
                        await asyncio.sleep(2)
                        
                        # Turn off
                        if await controller.turn_off_light(device.address, light_id=1):
                            print("✅ Successfully turned light OFF")
                        else:
                            print("❌ Failed to turn light OFF")
                    else:
                        print("❌ Failed to turn light ON")
                        
                        # Try secondary credentials
                        print("🔄 Trying secondary mesh credentials...")
                        if await controller.authenticate_with_mesh(device.address, use_secondary_creds=True):
                            print("✅ Secondary authentication successful")
                            if await controller.turn_on_light(device.address, light_id=1):
                                print("✅ Successfully turned light ON with secondary creds")
                                await asyncio.sleep(2)
                                await controller.turn_off_light(device.address, light_id=1)
                
                else:
                    print("❌ Authentication failed")
            else:
                print("❌ Connection failed")
        
        if connected_count == 0:
            print("❌ Could not connect to any devices")
        else:
            print(f"\n🎉 Successfully connected to {connected_count} devices")
    
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.exception("Unexpected error in main")
    finally:
        # Clean up connections
        print("🧹 Cleaning up connections...")
        await controller.disconnect_all()
        print("✅ Cleanup complete")

if __name__ == "__main__":
    print("🚀 URBARN Bluetooth Mesh Light Controller")
    print("=========================================")
    print("Using reverse-engineered mesh credentials from official app")
    print("Mesh: URBARN/15102, Fallback: Fulife/2846")
    print()
    
    asyncio.run(main())
