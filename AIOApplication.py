from PyQt4 import QtCore, QtGui
from game_version import GAME_VERSION
from ConfigParser import ConfigParser
import socket, struct, AIOprotocol, os, time
from AIOMainWindow import AIOMainWindow
from pybass import *


# taken from AIO python server code, it'll make my life easier.
def string_unpack(buf):
	unpacked = buf.split("\0")[0]
	gay = list(buf)
	for l in range(len(unpacked+"\0")):
		del gay[0]
	return "".join(gay), unpacked

def buffer_read(format, buffer):
	if format != "S":
		unpacked = struct.unpack_from(format, buffer)
		size = struct.calcsize(format)
		liss = list(buffer)
		for l in range(size):
			del liss[0]
		returnbuffer = "".join(liss)
		return returnbuffer, unpacked[0]
	else:
		return string_unpack(buffer)


class AIOApplication(QtGui.QApplication):
	player_id = -1
	charlist, musiclist, zonelist = [], [], []
	defaultzone = ""
	motd = ""
	music = None
	sound = None
	GUIsound = None
	sndvol = 100
	musicvol = 100
	blipvol = 100
	def __init__(self, argv=[]):
		super(AIOApplication, self).__init__(argv)
		self.tcpthread = ClientThread()
		self.mainwindow = AIOMainWindow(self)
		self.mainwindow.show()
	
	def startGame(self, player_id, defaultzone, motd, charlist, musiclist, zonelist, evidencelist):
		self.player_id = player_id
		self.defaultzone = defaultzone
		for i in range(len(zonelist)):
			if zonelist[i][0] == defaultzone:
				self.defaultzoneid = i
		self.motd = motd
		self.charlist = charlist
		self.musiclist = musiclist
		self.zonelist = zonelist
		self.evidencelist = evidencelist
		self.mainwindow.startGame()
	
	def stopGame(self):
		self.stopMusic()
		self.tcpthread.disconnect()
		self.mainwindow.stopGame()
	
	def playMusic(self, file):
		self.stopMusic()
		
		if os.path.exists("data\\sounds\\music\\"+file):
			filename, extension = os.path.splitext(file)
			extension = extension.lower()
			if extension == ".mod" or extension == ".mid" or extension == ".midi" or extension == ".xm" or extension == ".s3m" or extension == ".it":
				self.music = BASS_MusicLoad(False, "data\\sounds\\music\\"+file, 0, 0, 0, 0)
			else:
				self.music = BASS_StreamCreateFile(False, "data\\sounds\\music\\"+file, 0, 0, BASS_SAMPLE_LOOP)
			BASS_ChannelSetAttribute(self.music, BASS_ATTRIB_VOL, self.musicvol / 100.0)
			BASS_ChannelPlay(self.music, True)
		
	def playSound(self, file):
		if self.sound:
			if BASS_ChannelIsActive(self.sound):
				BASS_StreamFree(self.sound)
		
		if os.path.exists(file):
			self.sound = BASS_StreamCreateFile(False, file, 0, 0, 0)
			BASS_ChannelSetAttribute(self.sound, BASS_ATTRIB_VOL, self.sndvol / 100.0)
			BASS_ChannelPlay(self.sound, True)
	
	def playGUISound(self, file):
		if self.GUIsound:
			if BASS_ChannelIsActive(self.GUIsound):
				BASS_StreamFree(self.GUIsound)
		
		self.GUIsound = BASS_StreamCreateFile(False, file, 0, 0, 0)
		BASS_ChannelSetAttribute(self.GUIsound, BASS_ATTRIB_VOL, self.sndvol / 100.0)
		BASS_ChannelPlay(self.GUIsound, True)
	
	def stopMusic(self):
		if self.music:
			if BASS_ChannelIsActive(self.music):
				BASS_StreamFree(self.music)
				BASS_MusicFree(self.music)
	
	def connect(self, ip, port):
		self.tcpthread.disconnect()
		self.tcpthread.setAddress(ip, port)
		self.tcpthread.start()

class ClientThread(QtCore.QThread):
	disconnected = QtCore.pyqtSignal()
	connectionError = QtCore.pyqtSignal(str)
	gotWelcome = QtCore.pyqtSignal(list)
	gotCharacters = QtCore.pyqtSignal(list)
	gotMusic = QtCore.pyqtSignal(list)
	gotZones = QtCore.pyqtSignal(list)
	gotEvidence = QtCore.pyqtSignal(list)
	evidenceChanged = QtCore.pyqtSignal(list)
	kicked = QtCore.pyqtSignal(str)
	serverWarning = QtCore.pyqtSignal(str)
	movementPacket = QtCore.pyqtSignal(list)
	examinePacket = QtCore.pyqtSignal(list)
	playerCreate = QtCore.pyqtSignal(list)
	playerDestroy = QtCore.pyqtSignal(int)
	musicChange = QtCore.pyqtSignal(list)
	emoteSound = QtCore.pyqtSignal(list)
	OOCMessage = QtCore.pyqtSignal(list)
	ICMessage = QtCore.pyqtSignal(list)
	broadcastMessage = QtCore.pyqtSignal(list)
	chatBubble = QtCore.pyqtSignal(list)
	zoneChange = QtCore.pyqtSignal(list)
	charChange = QtCore.pyqtSignal(list)
	gotPing = QtCore.pyqtSignal(int)
	
	def __init__(self):
		super(ClientThread, self).__init__()
		self.connected = False
		self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.tcp.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
		self.ip = "0"
		self.port = 0
		
	def __del__(self):
		self.disconnect()
		self.wait()
	
	def setAddress(self, ip, port):
		self.ip = ip
		self.port = port
	
	def forceDisconnect(self, error=False):
		self.tcp.close()
		self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.connected = False
	
	def disconnect(self, error=False):
		if self.connected:
			self.forceDisconnect(error)
	
	def sendBuffer(self, buf):
		actualbuf = struct.pack("I", len(buf))
		actualbuf += buf
		self.tcp.sendall(str(actualbuf)+"\r")
	
	def sendWelcome(self):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.CONNECT)
			buf += GAME_VERSION+"\0"
			self.sendBuffer(buf)
	
	def sendRequest(self, type):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.REQUEST)
			buf += struct.pack("B", type)
			self.sendBuffer(buf)
	
	def sendIC(self, chatmsg, blip, color, realization, evidence):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.MSCHAT)
			buf += chatmsg+"\0"
			buf += blip+"\0"
			buf += struct.pack("I", color)
			buf += struct.pack("B", realization)
			buf += struct.pack("B", evidence)
			self.sendBuffer(buf)
	
	def sendOOC(self, name, chatmsg):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.OOC)
			buf += name+"\0"
			buf += chatmsg+"\0"
			self.sendBuffer(buf)
	
	def sendMusicChange(self, filename):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.MUSIC)
			buf += filename+"\0"
			self.sendBuffer(buf)
	
	def sendExamine(self, x, y):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.EXAMINE)
			buf += struct.pack("f", x)
			buf += struct.pack("f", y)
			self.sendBuffer(buf)
	
	def sendChatBubble(self, on):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.CHATBUBBLE)
			buf += struct.pack("B", on)
			self.sendBuffer(buf)
	
	def sendEmoteSound(self, soundname, delay):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.EMOTESOUND)
			buf += soundname+"\0"
			buf += struct.pack("I", delay)
			self.sendBuffer(buf)
	
	def setZone(self, zone):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.SETZONE)
			buf += struct.pack("H", zone)
			self.sendBuffer(buf)
	
	def setChar(self, char):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.SETCHAR)
			buf += struct.pack("h", char)
			self.sendBuffer(buf)
	
	def sendEvidence(self, type, *args):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.EVIDENCE)
			buf += struct.pack("B", type)
			if type == AIOprotocol.EV_ADD:
				name, desc, image = args
				buf += name+"\0"
				buf += desc+"\0"
				buf += image+"\0"
			elif type == AIOprotocol.EV_EDIT:
				ind, name, desc, image = args
				buf += struct.pack("B", ind)
				buf += name+"\0"
				buf += desc+"\0"
				buf += image+"\0"
			elif type == AIOprotocol.EV_DELETE:
				ind, = args
				buf += struct.pack("B", ind)
			else:
				return False
			
			self.sendBuffer(buf)
	
	def sendMovement(self, x, y, hspeed, vspeed, sprite, emoting, dir_nr):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.MOVE)
			buf += struct.pack("f", x)
			buf += struct.pack("f", y)
			buf += struct.pack("h", hspeed)
			buf += struct.pack("h", vspeed)
			buf += sprite+"\0"
			buf += struct.pack("B", emoting)
			buf += struct.pack("B", dir_nr)
			self.sendBuffer(buf)
	
	def sendPing(self):
		if self.connected:
			buf = struct.pack("B", AIOprotocol.PING)
			self.sendBuffer(buf)
	
	def run(self):
		tempdata = ""
		connection_phase = 0
		pingtimer = 7
		already_pinged = False
		
		try:
			self.tcp.connect((self.ip, self.port))
		except socket.error as err:
			self.connectionError.emit("Unable to connect to the selected server.\nAdditional information: %s" % err)
			self.forceDisconnect()
			return
		
		self.connected = True
		self.tcp.setblocking(False)
		self.sendWelcome()
		
		while True:
			if not self.connected:
				break
			
			can_send = int(time.time()) % pingtimer == 0
			if can_send and not already_pinged:
				pingbefore = time.time()
				already_pinged = True
				self.sendPing()
			elif not can_send:
				already_pinged = False
			
			try:
				data = self.tcp.recv(4096)
			except socket.error, err:
				if err.args[0] == 10035 or err.args[0] == "timed out":
					continue
				else:
					self.connectionError.emit("The connection to the server has been lost.\nAdditional information: %s" % err)
					self.disconnect()
					break
				
			if not data.endswith("\r"):
				tempdata += data
				continue
			else:
				if tempdata:
					data = tempdata+data
					tempdata = ""
			
			while data:
				data, header = buffer_read("B", data)
				#print header, repr(data)
				
				if header == AIOprotocol.CONNECT: #server default zone, maximum characters, MOTD...
					data, player_id = buffer_read("I", data)
					data, maxchars = buffer_read("I", data)
					data, defaultzone = buffer_read("S", data)
					data, maxmusic = buffer_read("I", data)
					data, maxzones = buffer_read("I", data)
					data, motd = buffer_read("S", data)
					if connection_phase == 0:
						self.gotWelcome.emit([player_id, maxchars, defaultzone, maxmusic, maxzones, motd.replace("#", "\n").replace("\\#", "#")])
						connection_phase += 1
						self.sendRequest(0)
				
				elif header == AIOprotocol.REQUEST:
					data, type = buffer_read("B", data)
					
					if type == 0: #characters
						charlist = []
						for i in range(maxchars):
							data, char = buffer_read("S", data)
							charlist.append(char)
						if connection_phase == 1:
							connection_phase += 1
							self.gotCharacters.emit(charlist)
							self.sendRequest(1)
					
					elif type == 1: #music
						musiclist = []
						for i in range(maxmusic):
							data, music = buffer_read("S", data)
							musiclist.append(music)
						if connection_phase == 2:
							connection_phase += 1
							self.gotMusic.emit(musiclist)
							self.sendRequest(2)
					
					elif type == 2: #zones
						zonelist = []
						for i in range(maxzones):
							data, zone = buffer_read("S", data)
							data, zonename = buffer_read("S", data)
							zonelist.append([zone, zonename])
						if connection_phase == 3:
							connection_phase += 1
							self.gotZones.emit(zonelist)
							self.sendRequest(3)
					
					elif type == 3: #evidence for spawn zone
						data, length = buffer_read("B", data)
						evidencelist = []
						for i in range(length):
							data, name = buffer_read("S", data)
							data, desc = buffer_read("S", data)
							data, image = buffer_read("S", data)
							evidencelist.append([name.decode("utf-8"), desc.decode("utf-8"), image.decode("utf-8")])
						if connection_phase == 4:
							connection_phase += 1
							self.gotEvidence.emit(evidencelist)
						
				elif header == AIOprotocol.KICK: #kicked.
					data, reason = buffer_read("S", data)
					self.kicked.emit(reason.replace("#", "\n").replace("\\#", "#")) #AIO was made in Game Maker 8, so it used hashes as newlines
					self.disconnect()
				
				elif header == AIOprotocol.MUSIC: #music change
					data, filename = buffer_read("S", data)
					data, char_id = buffer_read("I", data)
					data, zone = buffer_read("H", data)
					
					self.musicChange.emit([filename, char_id, zone])
					
				elif header == AIOprotocol.CREATE: #a player joins
					data, otherplayer = buffer_read("I", data)
					data, charid = buffer_read("h", data)
					data, zone = buffer_read("H", data)
					if otherplayer == player_id:
						continue
					
					self.playerCreate.emit([otherplayer, charid, zone])
				
				elif header == AIOprotocol.DESTROY: #a player leaves
					data, otherplayer = buffer_read("I", data)
					if otherplayer == player_id:
						continue
					
					self.playerDestroy.emit(otherplayer)
				
				elif header == AIOprotocol.EMOTESOUND:
					data, char_id = buffer_read("i", data)
					data, filename = buffer_read("S", data)
					data, sfx_delay = buffer_read("I", data)
					data, zone = buffer_read("H", data)
					
					self.emoteSound.emit([char_id, filename, sfx_delay, zone])
				
				elif header == AIOprotocol.MOVE: #player movements
					movepacket = []
					while not data.startswith("\r") and len(data) >= 22:
						data, client = buffer_read("I", data)
						data, x = buffer_read("f", data)
						data, y = buffer_read("f", data)
						data, hspeed = buffer_read("h", data)
						data, vspeed = buffer_read("h", data)
						data, sprite = buffer_read("S", data)
						data, emoting = buffer_read("B", data)
						data, dir_nr = buffer_read("B", data)
						movepacket.append([client, x, y, hspeed, vspeed, sprite, emoting, dir_nr])
					self.movementPacket.emit(movepacket)
			
				elif header == AIOprotocol.SETZONE:
					data, client = buffer_read("H", data)
					data, zone = buffer_read("H", data)
					self.zoneChange.emit([client, zone])
				
				elif header == AIOprotocol.SETCHAR:
					data, client = buffer_read("H", data)
					data, charid = buffer_read("h", data)
					self.charChange.emit([client, charid])
				
				elif header == AIOprotocol.EXAMINE:
					data, char_id = buffer_read("H", data)
					data, zone = buffer_read("H", data)
					data, x = buffer_read("f", data)
					data, y = buffer_read("f", data)
					self.examinePacket.emit([char_id, zone, x, y])
				
				elif header == AIOprotocol.OOC:
					data, name = buffer_read("S", data)
					data, message = buffer_read("S", data)
					self.OOCMessage.emit([name.decode("utf-8"), message.decode("utf-8")])
				
				elif header == AIOprotocol.MSCHAT:
					data, name = buffer_read("S", data)
					data, chatmsg = buffer_read("S", data)
					data, blip = buffer_read("S", data)
					data, zone = buffer_read("I", data)
					data, color = buffer_read("I", data)
					data, realization = buffer_read("B", data)
					data, clientid = buffer_read("I", data)
					data, evidence = buffer_read("B", data)
					
					self.ICMessage.emit([name, chatmsg, blip, zone, color, realization, clientid, evidence])
				
				elif header == AIOprotocol.BROADCAST:
					data, zone = buffer_read("h", data)
					data, message = buffer_read("S", data)
					self.broadcastMessage.emit([zone, message])
				
				elif header == AIOprotocol.CHATBUBBLE:
					data, cid = buffer_read("I", data)
					data, on = buffer_read("B", data)
					self.chatBubble.emit([cid, on])
				
				elif header == AIOprotocol.EVIDENCE:
					data, type = buffer_read("B", data)
					data, zone = buffer_read("B", data)
					ev_msg = [type, zone]
					
					if type == AIOprotocol.EV_ADD:
						data, name = buffer_read("S", data)
						data, desc = buffer_read("S", data)
						data, image = buffer_read("S", data)
						ev_msg.extend([name.decode("utf-8"), desc.decode("utf-8"), image.decode("utf-8")])
					elif type == AIOprotocol.EV_EDIT:
						data, ind = buffer_read("B", data)
						data, name = buffer_read("S", data)
						data, desc = buffer_read("S", data)
						data, image = buffer_read("S", data)
						ev_msg.extend([ind, name.decode("utf-8"), desc.decode("utf-8"), image.decode("utf-8")])
					elif type == AIOprotocol.EV_DELETE:
						data, ind = buffer_read("B", data)
						ev_msg.append(ind)
					elif type == AIOprotocol.EV_FULL_LIST:
						data, length = buffer_read("B", data)
						for i in range(length):
							data, name = buffer_read("S", data)
							data, desc = buffer_read("S", data)
							data, image = buffer_read("S", data)
							ev_msg.append([name.decode("utf-8"), desc.decode("utf-8"), image.decode("utf-8")])
					
					self.evidenceChanged.emit(ev_msg)
				
				elif header == AIOprotocol.WARN:
					data, message = buffer_read("S", data)
					self.serverWarning.emit(message.decode("utf-8"))
				
				elif header == AIOprotocol.PING:
					pingafter = time.time()
					self.gotPing.emit(int((pingafter - pingbefore)* 1000))
				
				if data:
					if data[0] == "\r":
						l = list(data)
						del l[0]
						data = "".join(l)