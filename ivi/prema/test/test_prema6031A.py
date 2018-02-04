"""

Python Interchangeable Virtual Instrument Library

Copyright (c) 2014-2017 Alex Forencich
Copyright (c) 2017-2018 Alson van der Meulen

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

from .. import prema6031A
from ... import ivi

class Virtual6031A(object):
    values = {
        'dc_volts': {
            '1': '+02.993543E-1MRVDP00A0R1F0T5D0S0Q0MOFB00',
            '2': '+09.993543E+0MRVDP00A0R2F0T5D0S0Q0MOFB00',
            '3': '+01.000003E+1MRVDP00A0R3F0T5D0S0Q0MOFB00',
        },
        'ac_volts': {
            '1': '+02.993543E-1MRVAP00A0R1F0T5D0S0Q0MOFB00',
            '2': '+09.993543E+0MRVAP00A0R2F0T5D0S0Q0MOFB00',
            '3': '+01.000003E+1MRVAP00A0R3F0T5D0S0Q0MOFB00',
        },
        'ac_plus_dc_volts': {
            '1': '+02.993543E-1MRVAP00A0R1F0T5D0S0Q0MOFB00',
            '2': '+09.993543E+0MRVAP00A0R2F0T5D0S0Q0MOFB00',
            '3': '+01.000003E+1MRVAP00A0R3F0T5D0S0Q0MOFB00',
        },
        'two_wire_resistance': {
            '1': '001.003103E+2MRO2P00A0R1F0T5D0S0Q0MOFB00',
            '2': '001.100039E+3MRO2P00A0R2F0T5D0S0Q0MOFB00',
            '3': '001.110215E+4MRO2P00A0R3F0T5D0S0Q0MOFB00',
        },
        'four_wire_resistance': {
            '1': '001.003103E+2MRO4P00A0R1F0T5D0S0Q0MOFB00',
            '2': '001.100039E+3MRO4P00A0R2F0T5D0S0Q0MOFB00',
            '3': '001.110215E+4MRO4P00A0R3F0T5D0S0Q0MOFB00',
        },
        'dc_current': {
            '5': '+00009.999E-2MRIDP00A0R5F0T5D0S0Q0MOFB00',
        },
        'ac_current': {
            '5': '+00009.999E-2MRIDP00A0R5F0T5D0S0Q0MOFB00',
        },
    }
    function_mapping = {
        'VD': 'dc_volts',
        'VA': 'ac_volts',
        'VC': 'ac_plus_dc_volts',
        'O2': 'two_wire_resistance',
        'O4': 'four_wire_resistance',
        'ID': 'dc_current',
        'IA': 'ac_current',
    }
    def __init__(self):
        self.read_buffer = io.BytesIO()
        self.tx_log = list()
        self.rx_log = list()
        self.cmd_log = list()
        self.trigger_mode = 'X'
        self.trigger_delay = 0
        self.function = 'dc_volts'
        self.range = '1'
        self.auto_range = False


    def write_raw(self, data):
        self.rx_log.append(data)
        cmd = data.split(b' ')[0].decode()

        #print("Got command %s" % cmd)

        # Ignore SCPI clear command that the IVI driver sets in absence of an
        # _interface.clear().
        if cmd.startswith('*CLS'): return
        # Handle the SCPI trigger command that the IVI driver sends in absence
        # of an _interface.trigger() that is not actually supported by this
        # meter.
        if cmd.startswith('*TRG'):
            self.cmd_log.append(cmd)
            self.read_buffer = io.BytesIO(self.values[self.function][self.range].encode())
            return

        # split command string in tokens
        token_re = re.compile(r'VD|VA|VC|O2|O4|ID|IA|TC|TK|TF|P\d\d *(?:CR)?|R\d|A\d|T\d|S\d|F\d|L\d|Q\d|D\d.*$|CT\d+$|CY[0-9+-E.]*$|M\d\d|MOF|ZO|CA(?:\d\d)+(ON|OFF)|TD\d+$|TO\d+$|TI\d+$|CR')
        for token in token_re.finditer(cmd):
            token = token.group(0)
            self.cmd_log.append(token)
            if token in self.function_mapping:
                self.function = self.function_mapping[token]
            m = re.match(r'R(\d)', token)
            if m:
                if 0 <= int(m.group(1)) <= 6:
                    self.range = m.group(1)
                else:
                    self.error()
                return
            m = re.match(r'A(\d)', token)
            if m:
                if m.group(1) == '0':
                    self.auto_range = False
                elif m.group(1) == '1':
                    self.auto_range = True

    def read_raw(self, num=-1):
        return self.read_buffer.read(num)

    def error(self):
        raise Exception


class TestPrema6031A(unittest.TestCase):

    def setUp(self):
        self.vdmm = Virtual6031A()
        self.dmm = prema6031A(self.vdmm)

    def test_measurement_function(self):
        mapping = (
            'dc_volts',
            'ac_volts',
            'ac_plus_dc_volts',
            'two_wire_resistance',
            'four_wire_resistance',
            'dc_current',
            'ac_current',
        )

        for func in mapping:
            self.dmm.measurement_function = func
            self.assertEqual(self.vdmm.function, func)
            self.assertEqual(self.dmm.measurement_function, func)
            self.dmm.measurement_function = 'dc_volts'
            self.assertEqual(self.vdmm.function, 'dc_volts')
            self.assertEqual(self.dmm.measurement_function, 'dc_volts')

    def test_range(self):
        funcs = {
            'dc_volts': ((1.9, '2', 9.993543), (4.0, '3', 10.00003)),
            'ac_volts': ((1.9, '2', 9.993543), (4.0, '3', 10.00003)),
            'ac_plus_dc_volts': ((1.9, '2', 9.993543), (4.0, '3', 10.00003)),
            'dc_current': ((1.9, '5', 9.999e-2),),
            'ac_current': ((1.9, '5', 9.999e-2),),
            'two_wire_resistance': ((1.9e3, '2', 1.100039E+3), (4e3, '3', 1.110215E+4)),
            'four_wire_resistance': ((1.9e3, '2', 1.100039E+3), (4e3, '3', 1.110215E+4)),
        }

        for func, ranges in funcs.items():
            self.dmm.measurement_function = func
            for (range_val, range_cmd, expected_result) in ranges:
                self.dmm.range = range_val
                self.assertEqual(self.vdmm.range, range_cmd)
                self.assertEqual(self.dmm.range, range_val)
                self.assertEqual(self.dmm.measurement.read(0), expected_result)

    def test_range_auto(self):
        funcs = [
            'dc_volts',
            'ac_volts',
            'dc_current',
            'ac_current',
            'two_wire_resistance',
            'four_wire_resistance',
        ]
        for func in funcs:
            self.dmm.measurement_function = func
            self.dmm.auto_range = 'on'
            self.assertTrue(self.vdmm.auto_range)
            self.assertEqual(self.dmm.auto_range, 'on')
            self.dmm.auto_range = 'off'
            self.assertFalse(self.vdmm.auto_range)
            self.assertEqual(self.dmm.auto_range, 'off')

if __name__ == '__main__':
    unittest.main()
