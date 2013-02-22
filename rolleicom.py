#!/usr/bin/env python

from serial import Serial

class RolleiCom():
    def __init__(self, *args, **kwargs):
        #ensure that a reasonable timeout is set
        timeout = kwargs.get('timeout', 0.1)
        if timeout < 0.01: timeout = 0.1
        kwargs['timeout'] = timeout
        self.serial = Serial(*args, **kwargs)
        self.PCMODE = None
        self.AF = True
        self.PAUSED = False
        self.EMITSLEFT = False
        self.EMITSRIGHT = False
        self.CODES = {'v': 'command accepted',
                      'B': 'busy',
                      'R': 'ready',
                      'g': 'not in pc mode',
                      'i': 'unknown command',
                      'e': '(mechanical) error',
                      'p': 'bad parameter',
                      'j': 'cmd processing',
                      '?': '<not implemented>'}

    def getstatus(self, verbose = False):
        # the char sent for status report is SMALL SHARP S in DOS codepage cp437
        self.serial.write(chr(225))
        if not verbose:
            return self.serial.read()
        else:
            return self.CODES[self.serial.read()]

    def connected(self):
        return self.getstatus() != ''

    def isbusy(self, getready = True):
        # queries if status codes indicate projector to be busy
        status = self.getstatus()
        busy = False
        if getready:
            busy = status is 'B'
        processing = status is 'v'
        return processing or busy

    def wait(self):
        # waits for command processing to finish
        # cmdonly only waits for command queue to clear
        while self.isbusy():
            continue

    def submit(self, cmd, wait = False, expectoutput = False):
        # send ASCII command to projector for execution
        while self.isbusy(getready = False):
            continue
        for char in cmd + '\r':
            self.serial.write(char)
            ret = self.serial.read()
            if ret is not char:
                if not self.connected():
                    return (False, None, 'Projector not online')
                print 'echo %s not %s' % (ret, char)
                self.serial.read(10)
        if expectoutput:
            out = self.serial.readline().strip()
        else:
            out = None
        # resubmit command if previous command is still processing
        if self.getstatus() is 'j':
            print self.CODES['j']
            self.submit(cmd, wait)
        if wait:
            self.wait()
        return (True, out, self.getstatus(verbose = True))

    def readmem(self, start, length, block = 'XData', quiet = True):
        # brightness: (6223, 2) oder evtl 38955
        # letzte lampcontrol (6187, 2) d.h. 200 201 202 204 204 205 206 und letzt gesetzte dissolve time auf byte 2
        # irgendeine lampe an (49385, 1) oder 16617   0x04 fuer an, 0x44 fuer alle aus
        # pc mode u.u. (16624, 2) 4e 67 fuer an 7e fe fuer aus oder u.u. 49392

        if not quiet:
            import sys

        if not 0 <= start <= 2**16-1:
            raise ValueError('Start read address is a value between 0 and 2**16-1 (0x00x00 to 0xff0xff)')

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

        outbuf = bytearray(length)

        self.serial.write(readcmd)
        out = self.serial.read()
        if not out == readcmd:
            if self.connected():
                raise Exception('port did not echo read command 0x02. (read %s)' % out.encode('hex'))
            else:
                raise Exception('Projector is offline')


        self.serial.write(starthex)
        out = self.serial.read(2)
        if not out == starthex:
            raise Exception('port did not echo start address "%s". (read %s)' % (starthex.encode('hex'), out.encode('hex')))

        self.serial.write(lengthhex)
        out = self.serial.read(2)
        if not out == lengthhex:
            raise Exception('port did not echo length "%s". (read %s)' % (lengthhex.encode('hex'), out.encode('hex')))

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
                sys.stdout.write('%s ' % cleaned.encode('hex'))

            if ord(out) < 0x10:
                raise Exception('read byte in escaped range, got to iteration %d. exiting (read %s)' % (byte, out.encode('hex')))

            self.serial.write(out)

        # if length == 1:
        #     # TODO: find out why it needs to be canceled for 1 byte read
        #     self.serial.write(stopcmd)
        #     out = self.serial.read(2)
        self.serial.write(stopcmd)
        out = self.serial.read()

        return outbuf

    def enterPCmode(self, wait = False):
        # enables PC mode, disables IR remote
        self.PCMODE = True
        return self.submit('PE', wait) # PC Modus einschalten

    def exitPCmode(self, wait = False):
        # exit PC mode, manual control via IR remote enabled
        # will only accept PE command subsequently
        self.PCMODE = False
        return self.submit('PA', wait) # PC Modus abschalten

    def reset(self, wait = False):
        # executes end function on projector and exits PC mode
        self.PCMODE = False
        return self.submit('RS', wait) # Reset

    def next(self, wait = False):
        # advance and show next slide; as green button
        return self.submit('BV', wait) # Bild vorwaerts

    def previous(self, wait = False):
        # reverse and show previous slide; as red button
        return self.submit('BR', wait) # Bild rueckwaerts

    def focusin(self, wait = False):
        # rack focus forward
        return self.submit('FV', wait) # Fokus vorwaerts

    def focusout(self, wait = False):
        # rack focus backward
        return self.submit('FR', wait) # Fokus rueckwaerts

    def enableAF(self, wait = False):
        # enable autofocus
        self.AF = True
        return self.submit('AE', wait) # Autofokus einschalten

    def disableAF(self, wait = False):
        # disable autofocus
        self.AF = False
        return self.submit('AA', wait) # Autofokus abschalten

    def toggleAF(self, wait = False):
        # toggle autofocus; as autofocus button on IR remote
        if self.AF:
            status = self.disableAF()
        else:
            status = self.enableAF()
        return (status[0], self.AF, status[2])

    def stop(self, wait = False):
        # pause projector
        self.PAUSED = True
        return self.submit('ST', wait) # Stop

    def go(self, wait = False):
        # resume projector
        self.PAUSED = False
        return self.submit('WE', wait) # Weiter

    def togglestop(self, wait = False):
        # stop and go toggle; as STOP/GO button on IR remote
        if self.PAUSED:
            status = self.go()
        else:
            status = self.stop()
        return (status[0], self.PAUSED, status[2])

    def end(self, wait = False):
        # end projection and rewind magazine; as END button on IR remote
        return self.submit('EN', wait) # Ende

    def currentline(self, wait = False):
        # get current line number in programme
        return self.submit('AZ', wait, expectoutput = True) # Aktuelle Zeile

    def currentslide(self, wait = False):
        # get number of currently loaded slide
        return self.submit('AB', wait, expectoutput = True) # Aktuelles Bild

    def readentry(self, line, wait = False):
        # read entry by line number from projection programme table
        try:
            line = int(line)
        except ValueError, v:
            return (False, None, 'Invalid line arg: ' + str(v))
        if not 0 <= line <= 255:
            raise ValueError('Line no. is a value between 0 and 255')
        cmd = 'LZ:%03d' % line # Lies Zeile
        return self.submit(cmd, wait, expectoutput = True) # Aktuelle Zeile

    def maxbrightness(self, brightness, wait = False):
        # set maximum brightness level for current slide show [001..255]
        try:
            brightness = int(brightness)
        except ValueError, v:
            return (False, None, 'Invalid brightness arg: ' + str(v))
        if not 0 <= brightness <= 255:
            raise ValueError('Brightness is a value between 0 and 255')
        cmd = 'SL:%03d' % brightness   # Setze Luminanz
        return self.submit(cmd, wait)

    def brightnessleft(self, brightness, wait = False):
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

    def brightnessright(self, brightness, wait = False):
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

    def lampcontrol(self, left = False, right = False, fade = False, wait = False):
        # switch lamps on or of with optional fade
        # `left`: bool
        # `right`: bool
        # `fade`: bool
        # set left or right to True or False to feed power to the respective lamps
        # the fade argument trigges a dissolve

        if left == right == False:
            cmd = (7,)
        elif left == False:
            if fade:
                cmd = (4,)
            else:
                cmd = (1, 2)
        elif right == False:
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

    def toggleleftlamp(self, wait = False):
        # toggle autofocus; as autofocus button on IR remote
        if self.EMITSLEFT:
            status = self.submit('LM:202', wait)
            self.EMITSLEFT = False
        else:
            status = self.submit('LM:200', wait)
            self.EMITSLEFT = True
        return (status[0], self.EMITSLEFT, status[2])

    def togglerightlamp(self, wait = False):
        # toggle autofocus; as autofocus button on IR remote
        if self.EMITSRIGHT:
            status = self.submit('LM:203', wait)
            self.EMITSRIGHT = False
        else:
            status = self.submit('LM:201', wait)
            self.EMITSRIGHT = True
        return (status[0], self.EMITSRIGHT, status[2])

    def dissolvefor(self, duration, wait = False):
        # set dissolve period in 10th of a second
        try:
            duration = int(duration)
        except ValueError, v:
            return (False, None, 'Invalid duration arg: ' + str(v))
        if not 0 <= duration <= 255:
            raise ValueError('Dissolve duration is a count of 0.1 second between 0 and 999')
        cmd = 'SD:%03d' % duration        # Setze Dissolvezeit
        return self.submit(cmd, wait)

    def loadleft(self, slide, wait = False):
        # load numbered slide into left condensor system; 0 clears
        if not 0 <= slide <= 255:
            raise ValueError('Slide number is a value between 0 and 255')
        cmd = 'B1:%03d' % slide        # Bild eins
        return self.submit(cmd, wait)

    def loadright(self, slide, wait = False):
        # load numbered slide into right condesor system; 0 clears
        if not 0 <= slide <= 255:
            raise ValueError('Slide number is a value between 0 and 255')
        cmd = 'B2:%03d' % slide        # Bild zwei
        return self.submit(cmd, wait)

    def goto(self, position, wait = False):
        raise RuntimeError('Does not work for some reason')
        if not 0 < position <= 50:
            raise ValueError('Slide number is a value between 0 and 255')

        self.reset()
        self.enterPCmode()
        self.focusin()

        while self.currentslide(wait = True) < position:
            self.focusin(wait = True)
        return self.currentslide()

    def firmwarerevision(self):
        memorypointer = 0xa0 + 42  # pointer table address plus offset 42
        address = int(str(self.readmem(memorypointer, 2, block = "Code")).encode('hex'), 16)
        length = int(str(self.readmem(memorypointer + 2, 2, block = "Code")).encode('hex'), 16)
        revision = str(self.readmem(address, length, block = "Code")).rstrip('\x00')
        return revision

