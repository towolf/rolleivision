#!/usr/bin/env python

from serial import Serial
import signal


class RolleiCom():
    def __init__(self, *args, **kwargs):
        #ensure that a reasonable timeout is set
        timeout = kwargs.get('timeout', 0.1)
        if timeout < 0.01:
            timeout = 0.05
        kwargs['timeout'] = timeout
        self.serial = Serial(*args, **kwargs)
        signal.signal(signal.SIGINT, self._sigint_handler)
        self.EMITSLEFT = False
        self.EMITSRIGHT = False
        self.RE_CMD = gen_cmd_regex()
        self.CODES = {'v': 'command accepted',
                      'B': 'busy',
                      'R': 'ready',
                      'g': 'not in pc mode',
                      'i': 'unknown command',
                      'e': '(mechanical) error',
                      'p': 'bad parameter',
                      'j': 'cmd processing',
                      '?': '<not implemented>'}
        self.SEGMENTMAP = {'\x7E': '0', '\x30': '1', '\x6D': '2', '\x79': '3',
                           '\x33': '4', '\x5B': '5', '\x5F': '6', '\x70': '7',
                           '\x7F': '8', '\x7B': '9', '\x77': 'A', '\x1F': 'b',
                           '\x4E': 'C', '\x3D': 'd', '\x4F': 'E', '\x47': 'F',
                           '\x67': 'P', '\x00': ' '}
        self.BATCH = '''
                     LOOP:
                     LD1:255     # Full brightness
                     LM:200      # Left lamp on
                     ST          # Pause (wait for remote)
                     LM:202      # Left lamp off
                     LD1:030     # Brightness 50
                     ST          # Pause
                     LM:200      # Left lamp on
                     SLEEP 5     # Wait 12 seconds
                     LM:202      # Left lamp off
                     ST          # Pause
                     # GOTO LOOP   # Jump
                     '''
        self.DEFAULTBATCH = self.BATCH

    def getstatus(self, verbose=False):
        # the char sent for status report is SMALL SHARP S in DOS codepage
        # cp437
        self.serial.write(chr(225))
        if not verbose:
            return self.serial.read()
        else:
            return self.CODES[self.serial.read()]

    def connected(self):
        return self.getstatus() != ''

    def isbusy(self, getready=True):
        # queries if status codes indicate projector to be busy
        status = self.getstatus()
        busy = False
        if getready:
            busy = status == 'B'
        processing = status == 'v'
        return processing or busy

    def wait(self):
        # waits for command processing to finish
        # cmdonly only waits for command queue to clear
        while self.isbusy():
            continue

    def submit(self, cmd, wait=False, expectoutput=False):
        # send ASCII command to projector for execution
        while self.isbusy(getready=False):
            continue
        for char in cmd + '\r':
            self.serial.write(char)
            ret = self.serial.read()
            if not ret == char:
                if not self.connected():
                    return (False, None, 'Projector not online')
                else:
                    self.serial.read(self.serial.inWaiting())
                    return (False, None,
                            'Projector echoed %s (%d) instead of %s (%d)'
                            % (ret, ord(ret), char, ord(char)))
        if expectoutput:
            out = self.serial.readline().strip()
        else:
            out = None
        # resubmit command if previous command is still processing
        if self.getstatus() is 'j':
            print self.CODES['j']
            self.submit(cmd, wait)
        if wait:
            while self.getstatus() != 'R':
                self.wait()
        return (True, out, self.getstatus(verbose=True))

    def readmem(self, start, length, block='XData', quiet=True):

        if not quiet:
            import sys

        if not 0 <= start <= 2**16-1:
            raise ValueError('Start address is a value between 0 and 2**16-1 (0x0000 to 0xffff)')

        if not 1 <= length <= 2**16-1:
            raise ValueError('Length is a value between 1 and 2**16-1 (0x00x01 to 0xff0xff)')

        starthex = ('%04x' % (start)).decode('hex')
        lengthhex = ('%04x' % (length)).decode('hex')

        if block == 'XData':
            readcmd = '\x01'
        elif block == 'Code':
            readcmd = '\x02'
        else:
            raise ValueError('memory block arg can be either "XData" or "Code"')
        stopcmd = '\x04'
        escapebyte = '\x10'
        offsetbyte = '\x80'

        def sendstop():
            self.serial.write(stopcmd)
            self.serial.read()

        outbuf = bytearray(length)

        self.serial.write(readcmd)
        out = self.serial.read()
        if not out == readcmd:
            sendstop()
            if self.connected():
                raise Exception('port did not echo read command 0x02. (read %s)' % out.encode('hex'))
            else:
                raise Exception('Projector is offline')

        for char in starthex:
            self.serial.write(char)
            out = self.serial.read()
            if not out == char:
                sendstop()
                err = (ord(char), ord(out), starthex.encode('hex'))
                raise Exception('got echo %02x for %02x in start address "%s". ' % err)

        for char in lengthhex:
            self.serial.write(char)
            out = self.serial.read()
            if not out == char:
                sendstop()
                err = (ord(char), ord(out), lengthhex.encode('hex'))
                raise Exception('got echo %02x for %02x in length "%s". ' % err)

        for byte in xrange(length):
            out = self.serial.read()
            if (byte % 32 == 0) and not quiet:
                sys.stdout.write('\n%08d : ' % (start + byte))
                sys.stdout.flush()

            if out == escapebyte:
                self.serial.write(escapebyte)
                out = self.serial.read()
                cleaned = chr(ord(out) - ord(offsetbyte))
            else:
                cleaned = out

            outbuf[byte] = cleaned

            if not quiet:
                sys.stdout.write("{0:02x} ".format(ord(cleaned)))

            if ord(out) < 0x10:
                sendstop()
                raise Exception('read byte in escaped range, got to iteration %d. exiting (read %s)' % (byte, out.encode('hex')))

            self.serial.write(out)

        if length == 1:
            # TODO: find out why it needs to be canceled for 1 byte read
            sendstop()

        return outbuf

    def enablePC(self, wait=False):
        # enables PC mode, disables IR remote
        return self.submit('PE', wait)  # PC Modus einschalten

    def disablePC(self, wait=False):
        # exit PC mode, manual control via IR remote enabled
        # will only accept PE command subsequently
        return self.submit('PA', wait)  # PC Modus abschalten

    def togglePC(self, wait=False):
        # toggle PC mode;
        PCMODE = self.queryPCmode()
        if PCMODE[1]:
            status = self.disablePC()
        else:
            status = self.enablePC()
        return self.queryPCmode()

    def reset(self, wait=False):
        # executes end function on projector and exits PC mode
        self.PCMODE = False
        return self.submit('RS', wait)  # Reset

    def next(self, wait=False):
        # advance and show next slide; as green button
        return self.submit('BV', wait)  # Bild vorwaerts

    def previous(self, wait=False):
        # reverse and show previous slide; as red button
        return self.submit('BR', wait)  # Bild rueckwaerts

    def focusin(self, wait=False):
        # rack focus forward
        return self.submit('FV', wait)  # Fokus vorwaerts

    def focusout(self, wait=False):
        # rack focus backward
        return self.submit('FR', wait)  # Fokus rueckwaerts

    def enableAF(self, wait=False):
        # enable autofocus
        return self.submit('AE', wait)  # Autofokus einschalten

    def disableAF(self, wait=False):
        # disable autofocus
        return self.submit('AA', wait)  # Autofokus abschalten

    def toggleAF(self, wait=False):
        # toggle autofocus; as autofocus button on IR remote
        AF = self.queryAF()
        if AF[1]:
            status = self.disableAF()
        else:
            status = self.enableAF()
        return self.queryAF()

    def stop(self, wait=False):
        # pause projector
        return self.submit('ST', wait)  # Stop

    def go(self, wait=False):
        # resume projector
        return self.submit('WE', wait)  # Weiter

    def togglestop(self, wait=False):
        # stop and go toggle; as STOP/GO button on IR remote
        stopped = self.querystopped()
        if stopped[1]:
            status = self.go()
        else:
            status = self.stop()
        return self.querystopped()

    def end(self, wait=False):
        # end projection and rewind magazine; as END button on IR remote
        return self.submit('EN', wait)  # Ende

    def currentline(self, wait=False):
        # get current line number in programme
        return self.submit('AZ', wait, expectoutput=True)  # Aktuelle Zeile

    def currentslide(self, wait=False):
        # get number of currently loaded slide
        return self.submit('AB', wait, expectoutput=True)  # Aktuelles Bild

    def readentry(self, line, wait=False):
        # read entry by line number from projection programme table
        try:
            line = int(line)
        except ValueError, v:
            return (False, None, 'Invalid line arg: ' + str(v))
        if not 0 <= line <= 255:
            raise ValueError('Line no. is a value between 0 and 255')
        cmd = 'LZ:%03d' % line  # Lies Zeile
        return self.submit(cmd, wait, expectoutput=True)  # Aktuelle Zeile

    def maxbrightness(self, brightness, wait=False):
        # set maximum brightness level for current slide show [001..255]
        try:
            brightness = int(brightness)
        except ValueError, v:
            return (False, None, 'Invalid brightness arg: ' + str(v))
        if not 0 <= brightness <= 255:
            raise ValueError('Brightness is a value between 0 and 255')
        cmd = 'SL:%03d' % brightness   # Setze Luminanz
        return self.submit(cmd, wait)

    def brightnessleft(self, brightness, wait=False):
        # set brightness in left condensor system [001..255]
        # requires dis- and re-enabling of the condensor lamp to become active
        try:
            brightness = int(brightness)
        except ValueError, v:
            return (False, None, 'Invalid brightness arg: ' + str(v))
        if not 0 <= brightness <= 255:
            raise ValueError('Brightness is a value between 0 and 255')
        cmd = 'LD1:%03d' % brightness   # Setze Luminanz
        return self.submit(cmd, wait)

    def brightnessright(self, brightness, wait=False):
        # set brightness in right condensor system [001..255]
        # requires dis- and re-enabling of the condensor lamp to become active
        try:
            brightness = int(brightness)
        except ValueError, v:
            return (False, None, 'Invalid brightness arg: ' + str(v))
        if not 0 <= brightness <= 255:
            raise ValueError('Brightness is a value between 0 and 255')
        cmd = 'LD2:%03d' % brightness   # Setze Luminanz
        return self.submit(cmd, wait)

    def lampcontrol(self, left=False, right=False, fade=False, wait=False):
        # switch lamps on or of with optional fade
        # `left`: bool
        # `right`: bool
        # `fade`: bool
        # set left or right to True or False to feed power to the respective
        # lamps the fade argument trigges a dissolve
        if not left and not right:
            cmd = (7,)
        elif not left:
            if fade:
                cmd = (4,)
            else:
                cmd = (1, 2)
        elif not right:
            if fade:
                cmd = (5,)
            else:
                cmd = (0, 3)
        else:
            cmd = (6,)

        success = []
        for x in cmd:
            status = self.submit('LM:20' + str(x), wait)
            success.append(status[0])
        return (success.count(False) is 0, None, status[2])

    def toggleleftlamp(self, wait=False):
        # toggle left lamp on and off; there a state tracking problem here, we
        # only know if any lamps are on, not which one
        emitting = self.querylamps()[1]
        if not emitting:
            self.EMITSLEFT = False
        if self.EMITSLEFT:
            status = self.submit('LM:202', wait)
            self.EMITSLEFT = False
        else:
            status = self.submit('LM:200', wait)
            self.EMITSLEFT = True
        return (status[0], self.EMITSLEFT, status[2])

    def togglerightlamp(self, wait=False):
        # toggle right lamp on and off; there a state tracking problem here, we
        # only know if any lamps are on, not which one
        emitting = self.querylamps()[1]
        if not emitting:
            self.EMITSRIGHT = False
        if self.EMITSRIGHT:
            status = self.submit('LM:203', wait)
            self.EMITSRIGHT = False
        else:
            status = self.submit('LM:201', wait)
            self.EMITSRIGHT = True
        return (status[0], self.EMITSRIGHT, status[2])

    def dissolvefor(self, duration, wait=False):
        # set dissolve period in 10th of a second for the PC mode functions
        try:
            duration = int(duration)
        except ValueError, v:
            return (False, None, 'Invalid duration arg: ' + str(v))
        if not 0 <= duration <= 255:
            raise ValueError('Dissolve duration is a count of 0.1 second between 0 and 999')
        cmd = 'SD:%03d' % duration        # Setze Dissolvezeit
        return self.submit(cmd, wait)

    def setdissolve(self, duration, wait=False):
        # set dissolve period in 10th of a second for the manual mode functions
        try:
            duration = int(duration)
        except ValueError, v:
            return (False, None, 'Invalid duration arg: ' + str(v))
        if not 0 <= duration <= 255:
            raise ValueError('Dissolve duration is a count of 0.1 second between 0 and 999')
        cmd = 'DZ:%03d' % duration        # Dissolvezeit
        return self.submit(cmd, wait)

    def loadleft(self, slide, wait=False):
        # load numbered slide into left condensor system; 0 clears
        try:
            slide = int(slide)
        except ValueError, v:
            return (False, None, 'Invalid slide arg: ' + str(v))
        if not 0 <= slide <= 255:
            raise ValueError('Slide number is a value between 0 and 255')
        cmd = 'B1:%03d' % slide        # Bild eins
        return self.submit(cmd, wait)

    def loadright(self, slide, wait=False):
        # load numbered slide into right condesor system; 0 clears
        try:
            slide = int(slide)
        except ValueError, v:
            return (False, None, 'Invalid slide arg: ' + str(v))
        if not 0 <= slide <= 255:
            raise ValueError('Slide number is a value between 0 and 255')
        cmd = 'B2:%03d' % slide        # Bild zwei
        return self.submit(cmd, wait)

    def gotoline(self, line, wait=False):
        # Go to line in programme table and commence show
        if not 0 <= line <= 999:
            raise ValueError('Slide number is a value between 0 and 999')
        cmd = 'GZ:%03d' % line        # Gehe zu Zeile
        return self.submit(cmd, wait)

    def gotoslide(self, slide, wait=False):
        # In Test mode: Commence show at first programme line containing slide
        # In Manual mode: Go to first programme line containing slide
        if not 0 <= slide <= 50:
            raise ValueError('Slide number is a value between 0 and 255')
        cmd = 'GB:%03d' % slide        # Gehe zu Bild
        return self.submit(cmd, wait)

    # Information derived from direct binary memory access
    #
    #  Discovered memory addresses for MSC 300P firmware V4.2
    #  6181 - last loaded slide left
    #  6183 - last loaded slide right
    #  6187 - last LM: command, i.e., as int [200..207]
    #  6188 - last set dissolve time
    #  6223 - last set brightness: two bytes 0..255
    # 16617 - bit 1 bin(1) 0 if AF is on; 1 if AF is off
    # 16617 - bit 2 bin(2) 0 if timer display is off; 1 if timer display is on
    # 16617 - bit 3 bin(4) 0 if dissolve display is off; 1 if dissolve display is on
    # 16617 - bit 6 bin(32) 0 if pause light is off; 1 if pause light is on
    # 16617 - bit 7 bin(64) 0 if any lamp on; 1 if both lamps off
    # 16618 - 3rd digit of slide number in 7-segment display
    # 16619 - 2nd digit of slide number in 7-segment display
    # 16620 - 1st digit of slide number in 7-segment display
    # 16621 - stop/go bit 7 bin(64) 0 if go and 1 if stopped
    # 16624 - last character in dissolve 7-segment display
    #         derive PC mode enable with bits bin(32)+bin(16) 0 if PC mode on and 1 otherwise
    # 16625 - second character in dissolve 7-segment display
    # 16626 - third character in dissolve 7-segment display
    # 16631 - timer LED on/off: bit 7 0 = aus, 1 = an
    # 16638 and 16641 - remote button currently being pressed
    #                   0 = no button being pressed
    #                   1 = end
    #                   2 = dissolve long
    #                   5 = focus out
    #                   7 = stop
    #                   9 = focus in
    #                  10 = dissolve medium
    #                  11 = forward
    #                  13 = backward
    #                  14 = dissolve short
    #                  15 = memo
    #                  16 = timer
    #                 128 = 0
    #                 129 = 1
    #                 130 = 2
    #                 131 = 3
    #                 132 = 4
    #                 133 = 5
    #                 134 = 6
    #                 135 = 7
    #                 136 = 8
    #                 137 = 9
    #                 192 = enter
    #                 193 = autofocus
    #                 194 = timer +
    #                 195 = timer -
    #                 196 = mode
    #                 197 = modul
    # 16640 - code of last pressed remote button

    def firmwarerevision(self):
        # Returns string of firmware version
        memorypointer = 0xa0 + 42  # pointer table address plus offset 42
        address = int(str(self.readmem(memorypointer, 2, block='Code')).encode('hex'), 16)
        length = int(str(self.readmem(memorypointer + 2, 2, block='Code')).encode('hex'), 16)
        revision = str(self.readmem(address, length, block='Code')).rstrip('\x00')
        return revision

    def queryPCmode(self):
        # Return True when PC mode is engaged
        # The three bytes from 16624 code 7-segment display to " PC"
        # or (0b01001110, 0b01100111, 0b00000000)
        return (True, self.readmem(16624, 3) == '\x4e\x67\x00', '')

    def querystopped(self):
        # Return True if stop/go function has paused the projector
        return (True, bool(ord(self.readmem(16621, 1)) & 64), '')

    def queryAF(self):
        # Return True if autofocus is enabled
        return (True, not ord(self.readmem(16617, 1)) & 1, '')

    def querylamps(self):
        # Returns True is any lamp is powered; False if all lamps are off
        return (True, not ord(self.readmem(16617, 1)) & 64, '')

    def queryloaded(self):
        # Returns tuple with slide number loaded last via loadleft and
        # loadright
        loaded = self.readmem(6181, 4)
        return (True, (loaded[0], loaded[2]), '')

    def querybrightness(self):
        # Returns tuple with current brightness (0..255, 0..255)
        brightness = self.readmem(6223, 2)
        return (True, (brightness[0], brightness[1]), '')

    def querydissolve(self):
        # Returns currently set dissolve time for next slide change
        return (True, ord(self.readmem(6188, 1)), '')

    def querydisplay(self):
        # Returns what is currently displayed in 3 digit 7-segment-display
        digits = []
        for byte in self.readmem(16624, 3):
            if byte > 128:
                digits.append(self.SEGMENTMAP[chr(byte ^ 128)] + '.')
            else:
                digits.append(self.SEGMENTMAP[chr(byte)])
        return (True, ''.join(reversed(digits)), '')

    # Batch command processing
    def getbatch(self, default=False):
        import textwrap
        if not default:
            batch = self.BATCH
        else:
            batch = self.DEFAULTBATCH
        return (True, textwrap.dedent(batch), 'returned batch script')
    # Batch command processing
    def runbatch(self, script):
        import time
        batch = [line.split('#')[0].strip() for line in script.splitlines()]
        valid = [self.RE_CMD.match(cmd) is not None for cmd in batch]
        if not all(valid):
            def validate(batch, errors):
                for line, valid in zip(batch, errors):
                    if valid:
                        yield line
                    else:
                        yield '<strong>' + line + '</strong>'
            markup = '\n'.join(validate(batch, valid))
            return (False, markup, 'Batch contains errors')
        self.BATCH = script
        for index, line in enumerate(batch):
            if not line or line.endswith(':'):
                pass
            elif line.startswith('SLEEP'):
                sleepfor = float(line.split()[1])
                time.sleep(sleepfor)
            elif line.startswith('GOTO'):
                label = line.split()[1]
                goto = batch.index(label + ':')
                return self.runbatch('\n'.join(batch[goto:]))  # TODO: ugly
            else:
                self.submit(line, wait=True)
            print "ran", index, line
        print self.BATCH
        return (True, script, 'ran {} lines'.format(index))

    def _sigint_handler(self, signal, frame):
        print '\n\nYou pressed Ctrl+C!\n\n'
        self.serial.flushOutput()
        if self.serial.inWaiting() > 0:
            print "Discarding %d waiting RX bytes" % self.serial.inWaiting()
            self.serial.flushInput()
        self.serial.write('\x04')
        if self.serial.read() == '\x04':
            print "Successfully cancelled TX"
        else:
            self.serial.readall()


def gen_cmd_regex():
    import re
    cmds = []
    cmds.append('\s*')
    cmds.append('SLEEP \d+(\.\d*)?')
    cmds.append('GOTO [A-Z]+')
    cmds.append('[A-Z]{4,}:')
    simple = ['PE', 'PA', 'RS', 'BV', 'BR', 'FV', 'FR', 'AE', 'AA', 'ST', 'WE',
              'EN', 'AZ', 'AB', 'MOM', 'MOT', 'MO', 'ML', 'MS']
    arg255 = ['DZ', 'SL', 'B1', 'B2', 'LD1', 'LD2', 'SD', 'BN', 'DI', 'GB']
    arg999 = ['SZ', 'BN', 'LZ', 'GZ']
    cmds.append('|'.join(simple))
    cmds.append('(' + '|'.join(arg255) + r'):[0-2]\d{2}')
    cmds.append('(' + '|'.join(arg999) + r'):\d{3}')
    cmds.append(r'SU:.[1-4][1-4]')
    cmds.append(r'LM:20[0-7]')
    cmds.append(r'TI:d{4}')
    cmds.append(r'SF:[0-4][0-7][0-9]')
    return re.compile('(' + r'|'.join(cmds) + ')(#.*)?$', re.MULTILINE)


def compare(lst):
    return lst[1:] == lst[:-1]


def comparebytearrays(*args):
    import sys
    for i in xrange(len(args[0])):
        items = [array[i] for array in args]
        if not compare(items):

            sys.stdout.write('%08d: ' % i)
            for byte in items:
                sys.stdout.write('%02x ' % byte)

            sys.stdout.write('    ')

            for byte in items:
                sys.stdout.write('%s ' % chr(byte).decode('cp437'))

            sys.stdout.write('\n')
            sys.stdout.flush()
