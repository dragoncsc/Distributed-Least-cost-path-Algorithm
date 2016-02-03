import sys
import collections
import socket
import copy
import threading
import select
import time
from time import strftime
'''
Distance Vector format:
	{
		(Node IP, Node Port) : (Node weight, (SourceIP, SourcePort))
	}

Neighbors:
	{
		(Node IP, Node Port) : (Node weight, timeSinceLastUpdate, on/off)
	}
'''

class bfclient(  ):

	def __init__( self, LocalPort, Timeout, _neighbors ):

		self.READONLYSOCK = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
		self.READONLYSOCK.bind( ( socket.gethostbyname( socket.gethostname() ), LocalPort ) )
		self.WRITESOCKET = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
		self.TIMEOUT = Timeout
		self.IP = socket.gethostbyname( socket.gethostname() )
		self.LocalPort = LocalPort

		self.neighborDV = {}
		self.neighbors = self.buildneighbors( _neighbors )
		self.newUpdate = False
		# build new dict for DV using neighbors
		# current nodes are immediately available so their links are themselves
		temp = {}
		__keys = self.neighbors.keys()
		for item in __keys:
			temp[ item ] = (self.neighbors[item][0], item)
		self.DistanceVector =  temp
		self.ALIVE = True


	def buildneighbors( self, _neighbors ):

		cur_neighbors = {}
		for node in _neighbors:
			IP = node[0]
			port = node[1]
			weight = node[2]
			cur_neighbors[ ( socket.gethostbyname(IP), port ) ] = (float(weight), time.time(), 1)
			self.neighborDV[ (socket.gethostbyname(IP), port) ] = {}

		return cur_neighbors


	def start( self ):
		# Main loop that starts listen thread, Listens to socket, listens to
		# user's input, tells users starts here too
		self.listen = threading.Thread( target=self.listenLoop )
		self.listen.start()
		self.updateNeighbors = threading.Thread( target=self.tellNeighbors )
		self.updateNeighbors.start()
		self.monitorNeighbors = threading.Thread( target=self.checkNeighbors)
		self.monitorNeighbors.start()
		
		#self.sendDV()
		while self.ALIVE:
			command = raw_input('What is thy bidding?\n')

			if len( command ) == 0:
				continue
			if command == 'SHOWRT':
				self.curDV = self.printDV(1)
			elif command == 'Nei':
				for k in self.neighbors:
					print k, " : ", self.neighbors[k]
				print 'Now distance:  '
				for k in self.DistanceVector:
					print k, " : ", self.DistanceVector[k]
			elif command == 'March to Helm\'s Deep':
				self.ALIVE = False
				sys.exit()
			elif command.split()[0] == 'LINKDOWN':
				self.takeDown( command )
			elif command.split()[0] == 'LINKUP':
				self.putUp( command )
			elif command == 'CLOSE':
				self.ALIVE = False
				sys.exit()
			else:
				print 'That was a pretty lame command dude'


	def listenLoop( self ):
		_in = [ self.READONLYSOCK ]
		_out = []

		while self.ALIVE == True:
			read, write, ex = select.select(_in, _out, _in, .01)
			if read:
				data, addr = read[0].recvfrom( 1024 )
				self.processDV( data )


	def processDV(  self, data  ):
		# User sent a message, process it and update DV as needed
		message = data.splitlines( )
		if message[0] == 'Route Update':
			_IP, _port, di = self.DVRouteUpdate( message )
			# see if node is in neighbors dictionary, if so, update time
			try:
				__cur__ = di[ ( self.IP, str(self.LocalPort) ) ]
				# updated link cost between the two
				if (__cur__[1], __cur__[2]) == ( self.IP, str(self.LocalPort) ):
					self.neighbors[ (_IP, _port) ] = ( __cur__[0], time.time(), 1 )
					# quick check to see if the we USE the direct route to this node, if so, update the path
					if self.DistanceVector[ (_IP, _port) ][1] == (_IP, _port):
						self.DistanceVector[ (_IP, _port) ] = ( __cur__[0], (_IP, _port) )
				# routes through another node to get to me, keep old cost just update time
				else:
					_k_ = self.neighbors[ (_IP, _port) ]
					self.neighbors[ (_IP, _port) ] = ( _k_[0], time.time(), _k_[2] )
			# not in list of neighbors, make new neighbor, dynamically add nodes to list
			except Exception, err:
				_cost = di[ ( self.IP, str(self.LocalPort) ) ][0]
				self.neighbors[ ( _IP, _port ) ] = ( _cost, time.time(), 1 )
				self.DistanceVector[ ( _IP, _port ) ] = ( _cost, ( _IP, _port ) )				
			self.ReCalculateRoute( _IP, _port, di )
			self.newUpdate = True

		elif message[0] == 'Link Down':
			self.DVLinkDown( message )
		elif message[0] =='Link Up':
			self.DVLinkUp( message )


	# Executive policy: DIRECT COST TO NEIGHBOR will be sored in self.neighbors, cheapest will be stored in self.distance
	def ReCalculateRoute( self, f_IP, f_port, dict_o_nebs ):
		# Reseting/creating neighbor's distance vector
		self.neighborDV[ (f_IP, f_port) ] = dict_o_nebs
		__k = self.neighborDV[ (f_IP, f_port) ].keys()

		# look through all keys in given distance vector
		for key in __k:
			# already delt with this case before entering loop
			if key == (self.IP, str(self.LocalPort) ):
				continue
			# we've already seen this node before, perhaps new DV offers a shorter path? make sure it avoids its own distance vector
			if key in self.DistanceVector:
				# check to see cost through this neighbor is cheaper than cur distance vector cost:
				if (float(self.neighborDV[(f_IP, f_port)][key][0])+float(self.DistanceVector[(f_IP, f_port)][0])) < float(self.DistanceVector[key][0]):
					# its true, so reroute though cur node and update cost in distance vector
					self.DistanceVector[key] = ( (float(self.neighborDV[(f_IP, f_port)][key][0])+float(self.DistanceVector[(f_IP, f_port)][0])), (f_IP,f_port) )
			# node is not in distance vector, add it to distance vector and update paths
			else:
				self.DistanceVector[key] = ( (float(self.neighborDV[(f_IP, f_port)][key][0])+float(self.DistanceVector[(f_IP, f_port)][0])), (f_IP,f_port) )

		__k = self.DistanceVector.keys()
		_neigh_keys = self.neighborDV.keys()

		for node in __k:
			for nei in _neigh_keys:
				if self.neighbors[nei][2] != 0 and node in self.neighborDV[nei]:
					# cost to this neighbor is cheaper than current cost
					if float(self.neighborDV[nei][node][0])+float(self.DistanceVector[nei][0]) < float(self.DistanceVector[node][0]):
						self.DistanceVector[node] = ( float(self.neighborDV[nei][node][0])+float(self.DistanceVector[nei][0]), self.DistanceVector[nei][1] )

		for node in __k:
			if node in self.neighbors and float(self.DistanceVector[node][0]) > float(self.neighbors[node][0]) and self.neighbors[node][2] != 0:
				self.DistanceVector[node] = ( float(self.neighbors[node][0]), node )

	# what i need to do: Find all nodes that route through the link that was taken down
	# if I find such a node, I need to iterate through all neighbors and see if there's another path
	# to that node. I need to iterate through all possible neighbors to ensure I calculate the shortest
	# path to that node. If there is no other path, I need some way of knowing this and need to later mark
	# the node with distance infinity
	def recalculateLinkDown( self, addr ):
		# get all keys
		_DVk = self.DistanceVector.keys()
		lock = threading.Lock()
		lock.acquire()
		
		# through all nodes in DV
		for key in _DVk:
			# current node routes through LINKDOWN node, need to find new path
			if self.DistanceVector[key][1] == addr:
				_neighs = self.neighborDV.keys()
				__t = self.DistanceVector[key]

				# reset node's distance for recalculation, set to direct link value or infinity
				if key in self.neighbors and self.neighbors[key][2] != 0:
					self.DistanceVector[key] = ( float(self.neighbors[key][0]), key )
				else:
					self.DistanceVector[key] = ( sys.maxint, __t[1] )
				# look through all neighbors to find another path
				for nn in _neighs:
					# skip this node, its bad for the following reasons:
					if nn == addr or nn not in self.neighbors or self.neighbors[nn][2] == 0:
						continue
					# current node doesn't route through this neighbor, nothing else to see here
					if key not in self.neighborDV[nn]:
						continue
					
					tup = self.neighborDV[nn][key]
					# route does not go through me or the downed node
					if (tup[1], tup[2]) != (self.IP, str(self.LocalPort)) and (tup[1], tup[2]) != addr and (tup[1], tup[2]) != key:
						# last check is there to make sure you don't route through node's own DV
						# new route is cheaper than old route
						if float(tup[0])+float(self.DistanceVector[nn][0]) > self.DistanceVector[key][0]:
							self.DistanceVector[key] = ( float(tup[0])+float(self.DistanceVector[nn][0]), nn )

		lock.release()

	# Linkup sequence
	def putUp( self, command ):
		try:
			IPaddr = socket.gethostbyname(command.split()[1])
			Port = command.split()[2]
		except:
			print "Bad link up command"
			return
		if (IPaddr, Port) in self.neighbors:
			message = "Link Up\n"+str(self.IP) + " " +str(self.LocalPort)
			self.WRITESOCKET.sendto( message, ( IPaddr, int(Port) ) )
			tup = self.neighbors[ (IPaddr, Port) ]
			self.neighbors[ (IPaddr, Port) ] = (tup[0], time.time(), 1)
			_tup = self.DistanceVector[ (IPaddr, Port) ]
			# Check to see if node is found by routing through another node, if not, then reset the link
			if float(self.DistanceVector[(IPaddr, Port)][0]) > float(self.neighbors[(IPaddr, Port)][0]):
				self.DistanceVector[ (IPaddr, Port) ] = ( tup[0], (IPaddr, Port) )
				self.ReCalculateRoute( IPaddr, Port, self.neighborDV[ (IPaddr, Port) ] )
			self.newUpdate = True
		else:
			print "The Link Up messaged inputted does not correspond to a known neighbor"


	def tellNeighbors( self ):
		
		curTime = time.time()
		while self.ALIVE:
			if self.newUpdate:
				self.sendDV()
				curTime = time.time()
				self.newUpdate = False
			if time.time() - curTime > self.TIMEOUT:
				self.sendDV()
				curTime = time.time()


	def checkNeighbors( self ):

		while self.ALIVE:
			_k_ = self.neighbors.keys()
			for keys in _k_:
				_c_ = self.neighbors[keys]
				if _c_[2] == 1 and (time.time() - float(_c_[1]) > self.TIMEOUT*3):
					tup = self.DistanceVector[keys]
					self.DistanceVector[ keys ] = ( sys.maxint, tup[1] )
					tup = self.neighbors[ keys ]
					self.neighbors[ keys ] = (tup[0], tup[1], 0)
					self.recalculateLinkDown( keys )



	def sendDV( self ):
		curDV = 'Route Update\n'+str(self.IP)+' '+str(self.LocalPort)+'\n'+self.printDV( 0 )
		__keys__ = self.neighbors.keys()

		for k in __keys__:
			_c_ = self.neighbors[k]
			if _c_[2] == 1:
				self.WRITESOCKET.sendto( curDV, ( k[0], int(k[1]) ) )


	def DVLinkDown( self, message ):
		_IP = socket.gethostbyname(message[1].split()[0])
		_port = message[1].split()[1]
		# Already out of commission
		if (_IP, _port) not in self.neighbors or self.neighbors[(_IP, _port)][2]==0:
			print "The Link Down message reiceved does not correspond to a once known neighbor"
			print "recieved: ", _IP, _port
			return
		#print self.neighbors
		if (_IP, _port) in self.DistanceVector:
			tup = self.DistanceVector[ (_IP, _port) ]
			self.DistanceVector[ (_IP, _port) ] = ( sys.maxint, tup[1] )
		tup = self.neighbors[ (_IP, _port) ]
		self.neighbors[ (_IP, _port) ] = (tup[0], time.time(), 0)
		self.recalculateLinkDown( (_IP, _port) )
		self.newUpdate = True


	def DVLinkUp( self, message ):
		_IP = socket.gethostbyname(message[1].split()[0])
		_port = message[1].split()[1]
		if (_IP, _port) not in self.neighbors:
			print "The Link up message reiceved does not correspond to a known neighbor"
			return
		tup = self.neighbors[ (_IP, _port) ]
		self.neighbors[ (_IP, _port) ] = (tup[0], time.time(), 1)		
		_tup = self.DistanceVector[ (_IP, _port) ]
		self.DistanceVector[ (_IP, _port) ] = ( tup[0], _tup[1] )
		self.ReCalculateRoute( _IP, _port, self.neighborDV[ (_IP, _port) ] )
		self.newUpdate = True



	'''
		These functions totally function
		SIKE
	'''

	def DVRouteUpdate( self, message ):

		f_IP = socket.gethostbyname(message[1].split()[0])
		f_port = message[1].split()[1]
		dict_o_nebs = {}
		for node in message[2:]:
			_node_vals = node.split(',')
			_t_ = _node_vals[0].split()
			curIP = _t_[1].split(':')[0]
			curPort = _t_[1].split(':')[1]
			cost = _node_vals[1].split()[1]
			_fromIP = _node_vals[2][3:-1]
			_fromPort = _node_vals[3][2:-2]
			dict_o_nebs[ (curIP, curPort) ] = (float(cost), _fromIP, _fromPort)

		_DV_keys = self.DistanceVector.keys()
		neb_keys = dict_o_nebs.keys()
		for __k in _DV_keys:
			if self.DistanceVector[__k][1] == (f_IP, f_port) and __k not in neb_keys and __k != (f_IP, f_port):
				_t = self.DistanceVector[__k]
				self.DistanceVector[ __k ] = ( sys.maxint, _t[1] )
		
		return f_IP, f_port, dict_o_nebs


	# Get DV
	def printDV( self, i ):

		__keys = self.DistanceVector.keys()
		_v_ = ''
		tru = True
		if i == 1:
			print '<'+strftime( "%Y-%m-%d %H:%M:%S" ) + '> Distance vector list is:'
		for item in __keys:
			if self.DistanceVector[item][0] == sys.maxint:
				continue
			
			if self.DistanceVector[item][1] == item and self.neighbors[item][2] == 0:
				continue

			'''
			if item in self.neighbors and self.neighbors[item][2] == 0:
				continue
			'''
			temp= ''.join(['Destination= ',str(item[0]),':',str(item[1]) ])
			temp= ''.join([temp,', ','Cost= ',str(self.DistanceVector[item][0])])
			temp= ''.join([temp,', ', str(self.DistanceVector[item][1])])
			_v_ += temp + '\n'
			if i == 1:
				print temp
		return _v_

	# I keep setting the Distance vector to MAX int, so recalculating distance would be easy in the recalculate distance
	# function. Then, in the LINKUP function, I just check the neighbor's weight against the current weight for LINKUP node in
	# the distance vector
	def takeDown( self, command ):
		try:
			IPaddr = socket.gethostbyname(command.split()[1])
			Port = command.split()[2]
		except:
			print "Bad link down command"
			return
		if (IPaddr, Port) in self.neighbors:
			message = "Link Down\n"+str(self.IP) + " " +str(self.LocalPort)
			self.WRITESOCKET.sendto( message, ( IPaddr, int(Port) ) )
			tup = self.DistanceVector[ (IPaddr, Port) ]
			# set to infinity if and only if a direct link is used to access node
			if tup[1] == (IPaddr, Port):
				self.DistanceVector[ (IPaddr, Port) ] = ( sys.maxint, tup[1] )
			tup = self.neighbors[ (IPaddr, Port) ]
			self.neighbors[ (IPaddr, Port) ] = (tup[0], tup[1], 0)
			self.recalculateLinkDown( (IPaddr, Port) )
			self.newUpdate = True
		else:
			print "The Link Down message reiceved does not correspond to a known neighbor"


# get my command line arguments

build_network = sys.argv
# parse args
if len(build_network)%3 != 0:
	print "Wrong number of arguments, must be multiple of three"
	sys.exit()
LocalPort = int( build_network[1] )
Timeout = int( build_network[2] )
num_neighbors = len(build_network[3:])/3
_neighbors = []
for i in range( 3, num_neighbors*3+1, 3 ):
	_neighbors.append( build_network[i : i+3] )


newClient = bfclient( LocalPort, Timeout, _neighbors)
newClient.start()

