
Command line arguments work as specified in project description. Here is an example to set up a four node circular network:
4 node least cost path link up/down tester:
- python bfclient.py 4115 30 12.168.132.147 4118 1.0 12.168.132.147 4116 30.0
- python bfclient.py 4118 30 12.168.132.147 4115 1.0 12.168.132.147 4117 1.0
- python bfclient.py 4117 30 12.168.132.147 4118 1.0 12.168.132.147 4116 1.0
- python bfclient.py 4116 30 12.168.132.147 4117 1.0 12.168.132.147 4115 30.0

this network will converge so that 4115 will have cost 3 to 4116, from an original cost of 30.


Senarios that work:
- Adding nodes that weren't initialized during the start of the program (on the command line). Nodes are added nicely and least cost paths are found. 
- Least cost path for a system of five nodes is attainable in a reasonable amount of time (after an appropiate number of messages have been sent)
- Timeouts work, updates are sent when nodes recieve updates.
- time is formatted appropiately
- I check to see if LINKDOWN/LINKUP actually correspond to neighbors and output error messages if they don't
- I check for proper user input
- I check for a multiple of three for a command line argument
- Link up work
- link down works for simple senarios

- Problem senario: 
	4115 --30-- 4117
	  |			  |
	  1    _______1
	  |   |
	  4118
	  The correct least cost path is found. If I break the Link between 4115 and 4118, 4115 gets the right cost path to all other nodes, but 4118 sees that 4117 has a path to 4115 of cost 2, adds its direct link cost to 4117, and gets a cost of 3 to 4115 instead of 31. Thus a self referential loop is started between 4117 and 4118. This should not be the case, (I think this is related to the count to infinity problem). 
	  BUT If I perform LINKUP between 4115 and 4118, all the costs reset to the correct cost.
	  The problem happens again if you added another node with cost 1 between 4118 and 4117, as 4115 gets the right cost to all nodes, but the other nodes route through each other and have innaccurate costs.



--> for any node whose cost is set to infinity, I don't display that value in SHOWRT



Important variables:
self.DistanceVector
	- dictionary, where the keys are the target nodes that are reachable from this current node, and values are tuples where the cost is the first index and the source node (the node that you route through to get to current node) is the second index. 
self.neighbors
	- Stores all known neighbors (nodes with direct links) to this current node.
	- key is the target node, and value is a tuple with cost as the first index, time of the last update as the second index, and a flag indicating whether the direct link is up/down as the the third index.
self.neighborDV
	- nested dictionaries
	- Stores most recent distance vector of all neighbors (first key)
		- value is a dictionary which is the distance vector of the current neighbor
		- this distance vector is built the same as the above distance vector



~~~ My protocol~~~

When a node has an  update, it sends Update Route message which is formatted:
		"
		Route Update
		(from IP, from Port)
		TargIP:TargPort, Cost, SourceIP:SourcePort
		(...)
		(...)
		(...) 
		"
Each neighbor node receives this message and parses it into a dictionary. It makes the TargIP and TargPort into a tuple which is used as a key, and the cost and SourceIP/SourcePort into another tuple which it indexes into the neighborDV which it stores in a dictionary of dictionaries, mapped by the tuple (Source IP, SourcePort) that sent the message.



When a user sends LINKDOWN message to a node it sends the following message to the downed node:
		"
		Link Down
		[from IP] [from Port]
		"
The receiving node parses the second line, and sets a flag in the neigbhors dictionary to 0, which signals to the node that this link is dead while keeping the original cost to the link. It sets the cost in the Distance Vector to infinity and then enters the recalculateLinkDown to see if there are any costs that will be altered by the downed link.


When a user sends LINKUP to a node, it sends this message to the reinstated node:
		"
		Link Up
		[from IP] [from Port]
		"
The target node reads the second line, sets the flag of the neighbors dictionary corresponding to the sending node to 1, which tells the node that this direct link is back up.

~~~ End of Protocol ~~~


--> Enter command 'Nei', so see all neighbors' distance vectors and your current distance vector (including infinity costs)


I have two main route computing fucntions: ReCalculateRoute and recalculateLinkDown.

==> ReCalculateRoute is there to reconfigure the route given some new Distance vector from a neighbor.

In this section: 
--> current distance vector means the current node's distance vector 
--> current neighbor distance vector means that some neighbor updated their distance vector and sent it to the current node, and that is what we're using to update the paths of known nodes.

- This function first walks through the new distance vector, and, given the target nodes in the current neighbor's distance vector, it updates them in the node's distance vector based on the cost in the current distance vector. If the cost to the current neighbor plus the cost to the node from that neighbor is greater than the current cost to that node, update the source node and the cost.
- Then, walk through ALL NODES in the distance vector of the current node, and see if any have to be updated. This step is necessary because the current neighbor might route through a link that was downed, and this would be reflected in the neighbor Distance vector, and if there was a node that routed through that link, the current node will update its cost to this other node by either setting its cost to infinity or rerouting.
- Finally, check all nodes in current distance vector to see if they are neighbors to the current node. If so, check the node's cost agaisnt its direct link cost, and if the direct link cost is cheaper, then use that in the current distance vector.



==> recalculateLinkDown is there to reconfigure the shortest path after a downed link was sent either by user or a neighbor node that broke their link
- acquire lock at the beginning of the function, because there are multiple threads accessing the current resource (sendDV and recieve messages)
- iterate through all nodes in the current distance vector. If the node routes through the downed link (the IP and port of which are args to this function), set the cost to either infinity, or its direct link cost
- then check all other nodes to see if there is a shorter path to this current node (that used to route through the downed node)
- release lock


==> for LINKUP, I just run ReCalculateRoute





