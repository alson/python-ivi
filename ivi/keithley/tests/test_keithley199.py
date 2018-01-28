"""

Python Interchangeable Virtual Instrument Library

Copyright (c) 2014-2017 Alex Forencich
Copyright (c) 2017 Alson van der Meulen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""

import io
import unittest
import re

from .. import keithley199
from ... import ivi

class Virtual199(object):
    values = {
        'dc_volts': {
            '0': 'NDCV+09.99354E+0,B000,C0',
            '1': 'NDCV+2.999354E-1,B000,C0',
            '2': 'NDCV+2.999354E+0,B000,C0',
            '3': 'NDCV+09.99354E+0,B000,C0',
        },
        'ac_volts': {
            '0': 'NACV+09.99354E+0,B000,C0',
            '1': 'NACV+2.999354E-1,B000,C0',
            '2': 'NACV+2.999354E+0,B000,C0',
            '3': 'NACV+09.99354E+0,B000,C0',
        },
        'resistance': {
            '0': 'NOHM+09.99354E+3,B000,C0',
            '1': 'NOHM+2.999354E+2,B000,C0',
            '2': 'NOHM+2.999354E+3,B000,C0',
            '3': 'NOHM+09.99354E+3,B000,C0',
        },
        'dc_current': {
            '0': 'NDCI+2.999354E+0,B000,C0',
            '1': 'NDCI+9.993545E-3,B000,C0',
            '2': 'NDCI+2.999354E+0,B000,C0',
            '3': 'NDCI+2.999354E+0,B000,C0',
        },
        'ac_current': {
            '0': 'NACI+2.999354E+0,B000,C0',
            '1': 'NACI+9.993545E-3,B000,C0',
            '2': 'NACI+2.999354E+0,B000,C0',
            '3': 'NACI+2.999354E+0,B000,C0',
        },
    }
    function_mapping = {
        '0': 'dc_volts',
        '1': 'ac_volts',
        '2': 'resistance',
        '3': 'dc_current',
        '4': 'ac_current',
    }
    trigger_mapping = {
        '2': 'GET',
        '3': 'GET',
        '4': 'X',
        '5': 'X',
        '6': 'ext',
        '7': 'ext',
    }
    def __init__(self):
        self.read_buffer = io.BytesIO()
        self.tx_log = list()
        self.rx_log = list()
        self.cmd_log = list()
        self.trigger_mode = 'X'
        self.trigger_delay = 0
        self.function = 'dc_volts'
        self.range = '0'


    def write_raw(self, data):
        self.rx_log.append(data)
        cmd = data.split(b' ')[0].decode()

        print("Got command %s" % cmd)

        # Ignore SCPI clear command that the IVI driver sets in absence of an
        # _interface.clear().
        if cmd.startswith('*CLS'): return
        # Handle the SCPI trigger command that the IVI driver sends in absence
        # of an _interface.trigger() that is not actually supported by this
        # meter.
        if cmd.startswith('*TRG'):
            self.cmd_log.append(cmd)
            return

        # split command string in tokens
        split_re = re.compile(r'([A-Z]\d*)')
        for token in split_re.finditer(cmd):
            token = token.group(1)
            print('T', token)
            self.cmd_log.append(token)
            if token == 'X' and self.trigger_mode == 'X':
                self.read_buffer = io.BytesIO(self.values[self.function][self.range].encode())
            m = re.match(r'R(\d)', token)
            if m:
                if 0 <= int(m.group(1)) <= 7:
                    self.range = m.group(1)
                else:
                    self.error()
                return
            m = re.match(r'F(\d)', token)
            if m:
                if 0 <= int(m.group(1)) <= 4:
                    self.function = self.function_mapping[m.group(1)]
                else:
                    self.error()
                return
            m = re.match(r'T(\d)', token)
            if m:
                if 0 <= int(m.group(1)) <= 7:
                    self.trigger_mode = self.trigger_mapping[m.group(1)]
                else:
                    self.error()
                return
            m = re.match(r'W(\d{1,6})', token)
            if m:
                self.trigger_delay = int(m.group(1))
                return


    def read_raw(self, num=-1):
        return self.read_buffer.read(num)

    def error(self):
        raise Exception


class TestKeithley199(unittest.TestCase):

    def setUp(self):
        self.vdmm = Virtual199()
        self.dmm = keithley199(self.vdmm)

    def test_measurement_function(self):
        mapping = {
            'dc_volts': 'F0',
            'ac_volts': 'F1',
            'two_wire_resistance': 'F2',
            'four_wire_resistance': 'F2',
            'dc_current': 'F3',
            'dc_current': 'F4',
        }

        for func in mapping.keys():
            self.dmm.measurement_function = func
            if not func.endswith('resistance'):
                self.assertEqual(self.vdmm.function, func)
            else:
                # 2W and 4W resistance share the same commands
                self.assertEqual(self.vdmm.function, 'resistance')
            self.assertEqual(self.dmm.measurement_function, func)
            self.dmm.measurement_function = 'dc_volts'
            self.assertEqual(self.vdmm.function, 'dc_volts')
            self.assertEqual(self.dmm.measurement_function, 'dc_volts')

    def test_range(self):
        funcs = {
            'dc_volts': ((2.0, '2', 2.999354), (4.0, '3', 9.99354)),
            'ac_volts': ((2.0, '2', 2.999354), (4.0, '3', 9.99354)),
            'dc_current': ((0.01, '1', 9.993545E-3), (2.9, '2', 2.999354)),
            'ac_current': ((0.01, '1', 9.993545E-3), (2.9, '2', 2.999354)),
            'two_wire_resistance': ((2e3, '2', 2.999354E+3), (4e3, '3', 9.99354E+3)),
            'four_wire_resistance': ((2e3, '2', 2.999354E+3), (4e3, '3', 9.99354E+3)),
        }

        for func, ranges in funcs.items():
            self.dmm.measurement_function = func
            for (range_val, range_cmd, expected_result) in ranges:
                self.dmm.range = range_val
                self.assertEqual(self.vdmm.range, range_cmd)
                self.assertEqual(self.dmm.range, range_val)
                self.assertEqual(self.dmm.measurement.read(), expected_result)

    def test_range_auto(self):
        funcs = [
            'dc_volts',
            'ac_volts',
            'dc_current',
            'ac_current',
            'two_wire_resistance',
            'four_wire_resistance',
        ]
        range_auto = '0'
        for func in funcs:
            self.dmm.measurement_function = func
            self.dmm.auto_range = 'on'
            self.assertEqual(self.vdmm.range, range_auto)
            self.assertEqual(self.dmm.auto_range, 'on')
            self.dmm.auto_range = 'off'
            self.assertNotEqual(self.vdmm.range, range_auto)
            self.assertEqual(self.dmm.auto_range, 'off')

    def test_trigger_delay(self):
        # Below 1ms resolution
        self.dmm.trigger.delay = 0.0001
        self.assertEqual(self.vdmm.trigger_delay, 0)
        self.assertEqual(self.dmm.trigger.delay, 0.0001)
        self.dmm.trigger.delay = 0.001
        self.assertEqual(self.vdmm.trigger_delay, 0.001*1000)
        self.assertEqual(self.dmm.trigger.delay, 0.001)
        # Max
        self.dmm.trigger.delay = 999.999
        self.assertEqual(self.vdmm.trigger_delay, 999.999*1000)
        self.assertEqual(self.dmm.trigger.delay, 999.999)
        # Over max
        with self.assertRaises(ivi.ValueNotSupportedException):
            self.dmm.trigger.delay = 1000

    def test_trigger_delay_auto(self):
        self.dmm.trigger.delay_auto = True
        self.assertEqual(self.vdmm.trigger_delay, 0)
        self.assertEqual(self.dmm.trigger.delay_auto, True)
        self.dmm.trigger.delay = 42
        self.assertEqual(self.vdmm.trigger_delay, 42000)
        self.assertEqual(self.dmm.trigger.delay_auto, False)
        self.dmm.trigger.delay_auto = False
        self.assertEqual(self.vdmm.trigger_delay, 42000)
        self.assertEqual(self.dmm.trigger.delay_auto, False)

    def test_trigger_source(self):
        mapping = {
            'bus': 'GET',
            'external': 'ext',
            'immediate': 'X'}
        for src in mapping:
            self.dmm.trigger.source = src
            self.assertEqual(self.vdmm.trigger_mode, mapping[src])
            self.assertEqual(self.dmm.trigger.source, src)
            self.dmm.trigger.source = 'immediate'
            self.assertEqual(self.vdmm.trigger_mode, mapping['immediate'])
            self.assertEqual(self.dmm.trigger.source, 'immediate')

    def test_measurement_initiate_fetch(self):
        self.range = '0'
        self.function = 'dc_volts'
        self.dmm.measurement.initiate()
        self.assertEqual(self.dmm.measurement.fetch(), 9.99354)
        # Check that the meter will not produce another measurement without
        # a read or initiate.
        with self.assertRaises(ivi.UnexpectedResponseException):
            self.dmm.measurement.fetch()

    def test_measurement_read(self):
        self.range = '0'
        self.function = 'dc_volts'
        self.assertEqual(self.dmm.measurement.read(), 9.99354)
        # Check that the meter will not produce another measurement without
        # a read or initiate.
        with self.assertRaises(ivi.UnexpectedResponseException):
            self.dmm.measurement.fetch()

    def test_trigger_multi_point_sample_count(self):
        for cache in (True, False):
            self.dmm.driver_operation.cache = cache
            self.dmm.trigger.multi_point.sample_count = 10
            self.assertEqual(self.vdmm.vals['sample:count'], 10)
            self.assertEqual(self.dmm.trigger.multi_point.sample_count, 10)
            self.dmm.trigger.multi_point.sample_count = 20
            self.assertEqual(self.vdmm.vals['sample:count'], 20)
            self.assertEqual(self.dmm.trigger.multi_point.sample_count, 20)
            self.vdmm.vals['sample:count'] = 30
            self.assertEqual(self.vdmm.vals['sample:count'], 30)
            if cache:
                self.assertEqual(self.dmm.trigger.multi_point.sample_count, 20)
            else:
                self.assertEqual(self.dmm.trigger.multi_point.sample_count, 30)

    def test_trigger_multi_point_count(self):
        for cache in (True, False):
            self.dmm.driver_operation.cache = cache
            self.dmm.trigger.multi_point.count = 10
            self.assertEqual(self.vdmm.vals['trigger:count'], 10)
            self.assertEqual(self.dmm.trigger.multi_point.count, 10)
            self.dmm.trigger.multi_point.count = 20
            self.assertEqual(self.vdmm.vals['trigger:count'], 20)
            self.assertEqual(self.dmm.trigger.multi_point.count, 20)
            self.vdmm.vals['trigger:count'] = 30
            self.assertEqual(self.vdmm.vals['trigger:count'], 30)
            if cache:
                self.assertEqual(self.dmm.trigger.multi_point.count, 20)
            else:
                self.assertEqual(self.dmm.trigger.multi_point.count, 30)

    def test_send_sofware_trigger(self):
        self.dmm.trigger.source = 'bus'
        self.dmm.send_software_trigger()
        self.assertEqual('*trg' in (cmd.lower() for cmd in self.vdmm.cmd_log), True)

if __name__ == '__main__':
    unittest.main()
