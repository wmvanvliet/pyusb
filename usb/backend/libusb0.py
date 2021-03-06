# Copyright (C) 2009-2011 Wander Lairson Costa 
# 
# The following terms apply to all files associated
# with the software unless explicitly disclaimed in individual files.
# 
# The authors hereby grant permission to use, copy, modify, distribute,
# and license this software and its documentation for any purpose, provided
# that existing copyright notices are retained in all copies and that this
# notice is included verbatim in any distributions. No written agreement,
# license, or royalty fee is required for any of the authorized uses.
# Modifications to this software may be copyrighted by their authors
# and need not follow the licensing terms described here, provided that
# the new terms are clearly indicated on the first page of each file where
# they apply.
# 
# IN NO EVENT SHALL THE AUTHORS OR DISTRIBUTORS BE LIABLE TO ANY PARTY
# FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES
# ARISING OUT OF THE USE OF THIS SOFTWARE, ITS DOCUMENTATION, OR ANY
# DERIVATIVES THEREOF, EVEN IF THE AUTHORS HAVE BEEN ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# 
# THE AUTHORS AND DISTRIBUTORS SPECIFICALLY DISCLAIM ANY WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.  THIS SOFTWARE
# IS PROVIDED ON AN "AS IS" BASIS, AND THE AUTHORS AND DISTRIBUTORS HAVE
# NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR
# MODIFICATIONS.

from ctypes import *
import ctypes.util
import os
import usb.backend
import usb.util
import sys
from usb.core import USBError
from usb._debug import methodtrace
import usb._interop as _interop
import logging

__author__ = 'Wander Lairson Costa'

__all__ = ['get_backend']

_logger = logging.getLogger('usb.backend.libusb0')

# usb.h

_PC_PATH_MAX = 4

if sys.platform.find('bsd') != -1 or sys.platform.find('mac') != -1 or \
        sys.platform.find('darwin') != -1:
    _PATH_MAX = 1024
elif sys.platform == 'win32' or sys.platform == 'cygwin':
    _PATH_MAX = 511
else:
    _PATH_MAX = os.pathconf('.', _PC_PATH_MAX)

# libusb-win32 makes all structures packed, while
# default libusb only does for some structures
# _PackPolicy defines the structure packing according
# to the platform.
class _PackPolicy(object):
    pass

if sys.platform == 'win32' or sys.platform == 'cygwin':
    _PackPolicy._pack_ = 1

# Data structures

class _usb_descriptor_header(Structure):
    _pack_ = 1
    _fields_ = [('blength', c_uint8),
                ('bDescriptorType', c_uint8)]

class _usb_string_descriptor(Structure):
    _pack_ = 1
    _fields_ = [('bLength', c_uint8),
                ('bDescriptorType', c_uint8),
                ('wData', c_uint16)]

class _usb_endpoint_descriptor(Structure, _PackPolicy):
    _fields_ = [('bLength', c_uint8),
                ('bDescriptorType', c_uint8),
                ('bEndpointAddress', c_uint8),
                ('bmAttributes', c_uint8),
                ('wMaxPacketSize', c_uint16),
                ('bInterval', c_uint8),
                ('bRefresh', c_uint8),
                ('bSynchAddress', c_uint8),
                ('extra', POINTER(c_uint8)),
                ('extralen', c_int)]

class _usb_interface_descriptor(Structure, _PackPolicy):
    _fields_ = [('bLength', c_uint8),
                ('bDescriptorType', c_uint8),
                ('bInterfaceNumber', c_uint8),
                ('bAlternateSetting', c_uint8),
                ('bNumEndpoints', c_uint8),
                ('bInterfaceClass', c_uint8),
                ('bInterfaceSubClass', c_uint8),
                ('bInterfaceProtocol', c_uint8),
                ('iInterface', c_uint8),
                ('endpoint', POINTER(_usb_endpoint_descriptor)),
                ('extra', POINTER(c_uint8)),
                ('extralen', c_int)]

class _usb_interface(Structure, _PackPolicy):
    _fields_ = [('altsetting', POINTER(_usb_interface_descriptor)),
                ('num_altsetting', c_int)]

class _usb_config_descriptor(Structure, _PackPolicy):
    _fields_ = [('bLength', c_uint8),
                ('bDescriptorType', c_uint8),
                ('wTotalLength', c_uint16),
                ('bNumInterfaces', c_uint8),
                ('bConfigurationValue', c_uint8),
                ('iConfiguration', c_uint8),
                ('bmAttributes', c_uint8),
                ('bMaxPower', c_uint8),
                ('interface', POINTER(_usb_interface)),
                ('extra', POINTER(c_uint8)),
                ('extralen', c_int)]

class _usb_device_descriptor(Structure, _PackPolicy):
    _pack_ = 1
    _fields_ = [('bLength', c_uint8),
                ('bDescriptorType', c_uint8),
                ('bcdUSB', c_uint16),
                ('bDeviceClass', c_uint8),
                ('bDeviceSubClass', c_uint8),
                ('bDeviceProtocol', c_uint8),
                ('bMaxPacketSize0', c_uint8),
                ('idVendor', c_uint16),
                ('idProduct', c_uint16),
                ('bcdDevice', c_uint16),
                ('iManufacturer', c_uint8),
                ('iProduct', c_uint8),
                ('iSerialNumber', c_uint8),
                ('bNumConfigurations', c_uint8)]

class _usb_device(Structure, _PackPolicy):
    pass

class _usb_bus(Structure, _PackPolicy):
    pass

_usb_device._fields_ = [('next', POINTER(_usb_device)),
                        ('prev', POINTER(_usb_device)),
                        ('filename', c_int8 * (_PATH_MAX + 1)),
                        ('bus', POINTER(_usb_bus)),
                        ('descriptor', _usb_device_descriptor),
                        ('config', POINTER(_usb_config_descriptor)),
                        ('dev', c_void_p),
                        ('devnum', c_uint8),
                        ('num_children', c_ubyte),
                        ('children', POINTER(POINTER(_usb_device)))]

_usb_bus._fields_ = [('next', POINTER(_usb_bus)),
                    ('prev', POINTER(_usb_bus)),
                    ('dirname', c_char * (_PATH_MAX + 1)),
                    ('devices', POINTER(_usb_device)),
                    ('location', c_uint32),
                    ('root_dev', POINTER(_usb_device))]

_usb_dev_handle = c_void_p

class _DeviceDescriptor:
    def __init__(self, dev):
        desc = dev.descriptor
        self.bLength = desc.bLength
        self.bDescriptorType = desc.bDescriptorType
        self.bcdUSB = desc.bcdUSB
        self.bDeviceClass = desc.bDeviceClass
        self.bDeviceSubClass = desc.bDeviceSubClass
        self.bDeviceProtocol = desc.bDeviceProtocol
        self.bMaxPacketSize0 = desc.bMaxPacketSize0
        self.idVendor = desc.idVendor
        self.idProduct = desc.idProduct
        self.bcdDevice = desc.bcdDevice
        self.iManufacturer = desc.iManufacturer
        self.iProduct = desc.iProduct
        self.iSerialNumber = desc.iSerialNumber
        self.bNumConfigurations = desc.bNumConfigurations
        self.address = dev.devnum
        self.bus = dev.bus[0].location
        
        self.port_number = None
_lib = None

def _load_library():
    if sys.platform != 'cygwin':
        candidates = ('usb-0.1', 'usb', 'libusb0')
        for candidate in candidates:
            # Workaround for CPython 3.3 issue#16283 / pyusb #14
            if sys.platform == 'win32':
                candidate = candidate + '.dll'

            libname = ctypes.util.find_library(candidate)
            if libname is not None: break
    else:
        # corner cases
        # cygwin predefines library names with 'cyg' instead of 'lib'
        try:
            return CDLL('cygusb0.dll')
        except:
            _logger.error('Libusb 0 could not be loaded in cygwin', exc_info=True)

        raise OSError('USB library could not be found')
    return CDLL(libname)

def _setup_prototypes(lib):
    # usb_dev_handle *usb_open(struct usb_device *dev);
    lib.usb_open.argtypes = [POINTER(_usb_device)]
    lib.usb_open.restype = _usb_dev_handle

    # int usb_close(usb_dev_handle *dev);
    lib.usb_close.argtypes = [_usb_dev_handle]

    # int usb_get_string(usb_dev_handle *dev,
    #                    int index,
    #                    int langid,
    #                    char *buf,
    #                    size_t buflen);
    lib.usb_get_string.argtypes = [
            _usb_dev_handle,
            c_int,
            c_int,
            c_char_p,
            c_size_t
        ]

    # int usb_get_string_simple(usb_dev_handle *dev,
    #                           int index,
    #                           char *buf,
    #                           size_t buflen);
    lib.usb_get_string_simple.argtypes = [
            _usb_dev_handle,
            c_int,
            c_char_p,
            c_size_t
        ]

    # int usb_get_descriptor_by_endpoint(usb_dev_handle *udev,
    #                                    int ep,
    #                                    unsigned char type,
    #                                    unsigned char index,
    #                                    void *buf,
    #                                    int size);
    lib.usb_get_descriptor_by_endpoint.argtypes = [
                                _usb_dev_handle,
                                c_int,
                                c_ubyte,
                                c_ubyte,
                                c_void_p,
                                c_int
                            ]

    # int usb_get_descriptor(usb_dev_handle *udev,
    #                        unsigned char type,
    #                        unsigned char index,
    #                        void *buf,
    #                        int size);
    lib.usb_get_descriptor.argtypes = [
                    _usb_dev_handle,
                    c_ubyte,
                    c_ubyte,
                    c_void_p,
                    c_int
                ]

    # int usb_bulk_write(usb_dev_handle *dev,
    #                    int ep,
    #                    const char *bytes,
    #                    int size,
    #                    int timeout);
    lib.usb_bulk_write.argtypes = [
            _usb_dev_handle,
            c_int,
            c_char_p,
            c_int,
            c_int
        ]

    # int usb_bulk_read(usb_dev_handle *dev,
    #                   int ep,
    #                   char *bytes,
    #                   int size,
    #                   int timeout);
    lib.usb_bulk_read.argtypes = [
            _usb_dev_handle,
            c_int,
            c_char_p,
            c_int,
            c_int
        ]

    # int usb_interrupt_write(usb_dev_handle *dev,
    #                         int ep,
    #                         const char *bytes,
    #                         int size,
    #                         int timeout);
    lib.usb_interrupt_write.argtypes = [
            _usb_dev_handle,
            c_int,
            c_char_p,
            c_int,
            c_int
        ]

    # int usb_interrupt_read(usb_dev_handle *dev,
    #                        int ep,
    #                        char *bytes,
    #                        int size,
    #                        int timeout);
    lib.usb_interrupt_read.argtypes = [
            _usb_dev_handle,
            c_int,
            c_char_p,
            c_int,
            c_int
        ]

    # int usb_control_msg(usb_dev_handle *dev,
    #                     int requesttype,
    #                     int request,
    #                     int value,
    #                     int index,
    #                     char *bytes,
    #                     int size,
    #                     int timeout);
    lib.usb_control_msg.argtypes = [
            _usb_dev_handle,
            c_int,
            c_int,
            c_int,
            c_int,
            c_char_p,
            c_int,
            c_int
        ]

    # int usb_set_configuration(usb_dev_handle *dev, int configuration);
    lib.usb_set_configuration.argtypes = [_usb_dev_handle, c_int]

    # int usb_claim_interface(usb_dev_handle *dev, int interface);
    lib.usb_claim_interface.argtypes = [_usb_dev_handle, c_int]

    # int usb_release_interface(usb_dev_handle *dev, int interface);
    lib.usb_release_interface.argtypes = [_usb_dev_handle, c_int]

    # int usb_set_altinterface(usb_dev_handle *dev, int alternate);
    lib.usb_set_altinterface.argtypes = [_usb_dev_handle, c_int]

    # int usb_resetep(usb_dev_handle *dev, unsigned int ep);
    lib.usb_resetep.argtypes = [_usb_dev_handle, c_int]

    # int usb_clear_halt(usb_dev_handle *dev, unsigned int ep);
    lib.usb_clear_halt.argtypes = [_usb_dev_handle, c_int]

    # int usb_reset(usb_dev_handle *dev);
    lib.usb_reset.argtypes = [_usb_dev_handle]

    # char *usb_strerror(void);
    lib.usb_strerror.argtypes = []
    lib.usb_strerror.restype = c_char_p

    # void usb_set_debug(int level);
    lib.usb_set_debug.argtypes = [c_int]

    # struct usb_device *usb_device(usb_dev_handle *dev);
    lib.usb_device.argtypes = [_usb_dev_handle]
    lib.usb_device.restype = POINTER(_usb_device)

    # struct usb_bus *usb_get_busses(void);
    lib.usb_get_busses.restype = POINTER(_usb_bus)

def _check(retval):
    if retval is None:
        errmsg = _lib.usb_strerror()
    else:
        ret = int(retval)
        if ret < 0:
            errmsg = _lib.usb_strerror()
            # No error means that we need to get the error
            # message from the return code
            # Thanks to Nicholas Wheeler to point out the problem...
            # Also see issue #2860940
            if errmsg.lower() == 'no error':
                errmsg = os.strerror(-ret)
        else:
            return ret
    raise USBError(errmsg, ret)

# implementation of libusb 0.1.x backend
class _LibUSB(usb.backend.IBackend):
    @methodtrace(_logger)
    def enumerate_devices(self):
        _check(_lib.usb_find_busses())
        _check(_lib.usb_find_devices())
        bus = _lib.usb_get_busses()
        while bool(bus):
            dev = bus[0].devices
            while bool(dev):
                yield dev[0]
                dev = dev[0].next
            bus = bus[0].next

    @methodtrace(_logger)
    def get_device_descriptor(self, dev):
        return _DeviceDescriptor(dev)

    @methodtrace(_logger)
    def get_configuration_descriptor(self, dev, config):
        if config >= dev.descriptor.bNumConfigurations:
            raise IndexError('Invalid configuration index ' + str(config))
        return dev.config[config]

    @methodtrace(_logger)
    def get_interface_descriptor(self, dev, intf, alt, config):
        cfgdesc = self.get_configuration_descriptor(dev, config)
        if intf >= cfgdesc.bNumInterfaces:
            raise IndexError('Invalid interface index ' + str(interface))
        interface = cfgdesc.interface[intf]
        if alt >= interface.num_altsetting:
            raise IndexError('Invalid alternate setting index ' + str(alt))
        return interface.altsetting[alt]

    @methodtrace(_logger)
    def get_endpoint_descriptor(self, dev, ep, intf, alt, config):
        interface = self.get_interface_descriptor(dev, intf, alt, config)
        if ep >= interface.bNumEndpoints:
            raise IndexError('Invalid endpoint index ' + str(ep))
        return interface.endpoint[ep]

    @methodtrace(_logger)
    def open_device(self, dev):
        return _check(_lib.usb_open(dev))

    @methodtrace(_logger)
    def close_device(self, dev_handle):
        _check(_lib.usb_close(dev_handle))

    @methodtrace(_logger)
    def set_configuration(self, dev_handle, config_value):
        _check(_lib.usb_set_configuration(dev_handle, config_value))

    @methodtrace(_logger)
    def set_interface_altsetting(self, dev_handle, intf, altsetting):
        _check(_lib.usb_set_altinterface(dev_handle, altsetting))

    @methodtrace(_logger)
    def get_configuration(self, dev_handle):
        bmRequestType = usb.util.build_request_type(
                                usb.util.CTRL_IN,
                                usb.util.CTRL_TYPE_STANDARD,
                                usb.util.CTRL_RECIPIENT_DEVICE
                            )
        return self.ctrl_transfer(dev_handle,
                                  bmRequestType,
                                  0x08,
                                  0,
                                  0,
                                  1,
                                  100
                            )[0]
                                  

    @methodtrace(_logger)
    def claim_interface(self, dev_handle, intf):
        _check(_lib.usb_claim_interface(dev_handle, intf))

    @methodtrace(_logger)
    def release_interface(self, dev_handle, intf):
        _check(_lib.usb_release_interface(dev_handle, intf))

    @methodtrace(_logger)
    def bulk_write(self, dev_handle, ep, intf, data, timeout):
        return self.__write(_lib.usb_bulk_write,
                            dev_handle,
                            ep,
                            intf,
                            data, timeout)

    @methodtrace(_logger)
    def bulk_read(self, dev_handle, ep, intf, data, size, timeout):
        return self.__read(_lib.usb_bulk_read,
                           dev_handle,
                           ep,
                           intf,
                           data,
                           size,
                           timeout)

    @methodtrace(_logger)
    def intr_write(self, dev_handle, ep, intf, data, timeout):
        return self.__write(_lib.usb_interrupt_write,
                            dev_handle,
                            ep,
                            intf,
                            data,
                            timeout)

    @methodtrace(_logger)
    def intr_read(self, dev_handle, ep, intf, data, size, timeout):
        return self.__read(_lib.usb_interrupt_read,
                           dev_handle,
                           ep,
                           intf,
                           data,
                           size,
                           timeout)

    @methodtrace(_logger)
    def ctrl_transfer(self,
                      dev_handle,
                      bmRequestType,
                      bRequest,
                      wValue,
                      wIndex,
                      data_or_wLength,
                      timeout):
        if usb.util.ctrl_direction(bmRequestType) == usb.util.CTRL_OUT:
            address, length = data_or_wLength.buffer_info()
            length *= data_or_wLength.itemsize
            return _check(_lib.usb_control_msg(
                                dev_handle,
                                bmRequestType,
                                bRequest,
                                wValue,
                                wIndex,
                                cast(address, c_char_p),
                                length,
                                timeout
                            ))
        else:
            data = _interop.as_array((0,) * data_or_wLength)
            read = int(_check(_lib.usb_control_msg(
                                dev_handle,
                                bmRequestType,
                                bRequest,
                                wValue,
                                wIndex,
                                cast(data.buffer_info()[0],
                                     c_char_p),
                                data_or_wLength,
                                timeout
                            )))
            return data[:read]

    @methodtrace(_logger)
    def reset_device(self, dev_handle):
        _check(_lib.usb_reset(dev_handle))

    @methodtrace(_logger)
    def detach_kernel_driver(self, dev_handle, intf):
        _check(_lib.usb_detach_kernel_driver_np(dev_handle, intf))

    def __write(self, fn, dev_handle, ep, intf, data, timeout):
        address, length = data.buffer_info()
        length *= data.itemsize
        return int(_check(fn(
                        dev_handle,
                        ep,
                        cast(address, c_char_p),
                        length,
                        timeout
                    )))

    def __read(self, fn, dev_handle, ep, intf, data, size, timeout):
        read_into = (data != None)
        if not read_into:
            data = _interop.as_array((0,) * size)
        address, length = data.buffer_info()
        length *= data.itemsize
        ret = int(_check(fn(
                    dev_handle,
                    ep,
                    cast(address, c_char_p),
                    length,
                    timeout
                )))
        if read_into:
            return ret
        else:
            return data[:ret]

def get_backend():
    global _lib
    try:
        if _lib is None:
            _lib = _load_library()
            _setup_prototypes(_lib)
            _lib.usb_init()
        return _LibUSB()
    except Exception:
        _logger.error('Error loading libusb 0.1 backend', exc_info=True)
        return None
