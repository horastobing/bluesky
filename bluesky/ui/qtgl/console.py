""" Console interface for the QTGL implementation."""
try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QWidget, QTextEdit
except ImportError:
    from PyQt4.QtCore import Qt
    from PyQt4.QtGui import QWidget, QTextEdit

import bluesky as bs
from bluesky.tools.misc import cmdsplit
from bluesky.tools.signal import Signal
from . import autocomplete

cmdline_stacked = Signal()

def get_cmd():
    """ Return the current command in the console's command line."""
    if not Console._instance:
        return ''
    return Console._instance.cmd


def get_cmdline():
    """ Return the current text in the console's command line."""
    if not Console._instance:
        return ''
    return Console._instance.command_line


def get_args():
    """ Return the current command arguments in the console's command line."""
    if not Console._instance:
        return []
    return Console._instance.args


def stack(text):
    assert Console._instance is not None, 'No console created yet: can only stack' + \
        ' after main window is created.'
    Console._instance.stack(text)


def append_cmdline(text):
    assert Console._instance is not None, 'No console created yet: can only change' + \
        ' command line after main window is created.'
    Console._instance.append_cmdline(text)


class Console(QWidget):
    lineEdit = None
    stackText = None
    _instance = None

    def __init__(self, parent=None):
        super(Console, self).__init__(parent)
        self.command_history = []
        self.cmd             = ''
        self.args            = []
        self.history_pos     = 0
        self.command_mem     = ''
        self.command_line    = ''

        # Connect to the io client's activenode changed signal
        bs.net.event_received.connect(self.on_simevent_received)
        bs.net.actnodedata_changed.connect(self.actnodedataChanged)

        assert Console._instance is None, "Console constructor: console instance " + \
            "already exists! Cannot have more than one console."
        Console._instance = self

    def on_simevent_received(self, eventname, eventdata, sender_id):
        ''' Processing of events from simulation nodes. '''
        if eventname == b'CMDLINE':
            self.set_cmdline(eventdata)

    def actnodedataChanged(self, nodeid, nodedata, changed_elems):
        if 'ECHOTEXT' in changed_elems:
            self.stackText.setPlainText(nodedata.echo_text)
            self.stackText.verticalScrollBar().setValue(self.stackText.verticalScrollBar().maximum())


    def stack(self, text):
        # Add command to the command history
        self.command_history.append(text)
        self.echo(text)
        # Send stack command to sim process
        bs.net.send_event(b'STACKCMD', text)
        cmdline_stacked.emit(self.cmd, self.args)
        # reset commandline and the autocomplete history
        self.set_cmdline('')
        autocomplete.reset()
        self.history_pos = 0

    def echo(self, text):
        actdata = bs.net.get_nodedata()
        actdata.echo(text)
        self.stackText.append(text)
        self.stackText.verticalScrollBar().setValue(self.stackText.verticalScrollBar().maximum())

    def append_cmdline(self, text):
        self.set_cmdline(self.command_line + text)

    def set_cmdline(self, text):
        if self.command_line == text:
            return

        actdata = bs.net.get_nodedata()

        self.command_line = text
        self.cmd, self.args = cmdsplit(self.command_line)
        self.cmd = self.cmd.upper()

        hintline = ''
        allhints = actdata.stackcmds
        if allhints:
            hint = allhints.get(self.cmd)
            if hint:
                if len(self.args) > 0:
                    hintargs = hint.split(',')
                    hintline = ' ' + str.join(',', hintargs[len(self.args):])
                else:
                    hintline = ' ' + hint

        self.lineEdit.setHtml('>>' + self.command_line + '<font color="#aaaaaa">' + hintline + '</font>')

    def keyPressEvent(self, event):
        ''' Handle keyboard input for bluesky. '''
        # Enter-key: enter command
        if event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return:
            if self.command_line:
                # emit a signal with the command for the simulation thread
                self.stack(self.command_line)
                # Clear any shape command preview on the radar display
                # self.radarwidget.previewpoly(None)
                return

        newcmd = self.command_line
        if event.key() == Qt.Key_Backspace:
            newcmd = newcmd[:-1]

        elif event.key() == Qt.Key_Up:
            if self.history_pos == 0:
                self.command_mem = newcmd
            if len(self.command_history) >= self.history_pos + 1:
                self.history_pos += 1
                newcmd = self.command_history[-self.history_pos]

        elif event.key() == Qt.Key_Down:
            if self.history_pos > 0:
                self.history_pos -= 1
                if self.history_pos == 0:
                    newcmd = self.command_mem
                else:
                    newcmd = self.command_history[-self.history_pos]

        elif event.key() == Qt.Key_Tab:
            if newcmd:
                newcmd, displaytext = autocomplete.complete(newcmd)
                if displaytext:
                    self.echo(displaytext)

        elif event.key() >= Qt.Key_Space and event.key() <= Qt.Key_AsciiTilde:
            newcmd += str(event.text())

        else:
            # Remaining keys are things like sole modifier keys, and function keys
            super(Console, self).keyPressEvent(event)

        # Final processing of the command line
        self.set_cmdline(newcmd)

class Cmdline(QTextEdit):
    def __init__(self, parent=None):
        super(Cmdline, self).__init__(parent)
        Console.lineEdit = self
        self.setFocusPolicy(Qt.NoFocus)
        self.setHtml('>>')


class Stackwin(QTextEdit):
    def __init__(self, parent=None):
        super(Stackwin, self).__init__(parent)
        Console.stackText = self
        self.setFocusPolicy(Qt.NoFocus)
