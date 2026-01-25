Run the server on your computer and connect to it with a touch screen device like a phone or iPad to use it as a MIDI controller with an isomorphic keyboard.
Python can only do MIDI **output** so get something like loopMIDI which can create a pair of linked virtual MIDI devices so that when python outputs to one it sends input to the other.
You'll probably have to configure the MIDI port name in the code, I call mine PythonMIDI.
the number at the end of the port name is important and added automatically by loopMIDI to distinguish the input and output ports (I think).
