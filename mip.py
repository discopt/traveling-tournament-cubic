from xml.dom.minidom import parse, parseString
import sys
from gurobipy import *

# Read instance.

dom = parse(sys.argv[1])
instanceName = dom.getElementsByTagName('InstanceName')[0].childNodes[0].data

teamNames = { int(tag.attributes['id'].value): tag.attributes['name'].value for tag in dom.getElementsByTagName("team") }
teams = list(teamNames.keys())
n = len(teams)

slotNames = { int(tag.attributes['id'].value): tag.attributes['name'].value for tag in dom.getElementsByTagName("slot") }
slots = list(slotNames.keys())
m = len(slots)

distances = {}
for tag in dom.getElementsByTagName('distance'):
  distances[int(tag.attributes['team1'].value), int(tag.attributes['team2'].value)] = float(tag.attributes['dist'].value)

# All instances have these properties anyway.
maxConsecutiveHome = 3
maxConsecutiveAway = 3
nonRepeater = True

# Check if mirrored:
mirrored = False
for tag in dom.getElementsByTagName('gameMode'):
  if tag.childNodes[0].data == 'M':
    mirrored = True

print(f'Parsed instance <{instanceName}>: {n} teams, non-repeater={nonRepeater}, max-consec-home={maxConsecutiveHome}, max-consec-away={maxConsecutiveAway}, mirrored={mirrored}')

assert m == 2*n - 2
assert len(distances) == n**2

matches = [ (k,i,j) for k in slots for i in teams for j in teams if i != j ]
arcs = [ (i,j) for i in teams for j in teams if i != j ]

options = sys.argv[2:]

# Set up model.
varType = GRB.BINARY if 'ip' in options else GRB.CONTINUOUS
addFlow = '8' in options
addFlowEquations = '10' in options
addFlowHome = '8+' in options
addHomeFlow = '9' in options
addLiftedQuadDiff = '5' in options
addLiftedQuadSame = '67' in options
addTranslatedHomeFlow = '14' in options

model = Model('TTP')
model.params.threads = 1
model.params.timeLimit = 3600

x = {}
for k,i,j in matches:
  x[k,i,j] = model.addVar(name=f'x#{k}#{teamNames[i]}#{teamNames[j]}', vtype=varType)
y = {}
for t in teams:
  for i,j in arcs:
    y[t,i,j] = model.addVar(name=f'y#{teamNames[t]}#{teamNames[i]}#{teamNames[j]}', vtype=varType, obj=distances[i,j])

model.update()

# (1b)
for k in slots:
  if k > 0:
    for i in teams:
      model.addConstr( quicksum( x[k,i,j] + x[k,j,i] for j in teams if j != i ) == 1, f'1b#{k}#{teamNames[i]}')

# (1c)
for i,j in arcs:
  model.addConstr( quicksum( x[k,i,j] for k in slots ) == 1, f'1c#{k}#{teamNames[i]}#{teamNames[j]}')

# (1d)
for k in slots:
  if k != m-1:
    for i,j in arcs:
      for t in teams:
        if t != i and t != j:
          model.addConstr( x[k,i,t] + x[k+1,j,t] - 1 <= y[t,i,j] )

# (1e)
for k in slots:
  if k != m-1:
    for t,j in arcs:
      model.addConstr( quicksum( x[k,t,i] for i in teams if i != t ) + x[k+1,j,t] - 1 <= y[t,t,j] )

# (1f)
for k in slots:
  if k != 0:
    for i,t in arcs:
      model.addConstr( x[k-1,i,t] + quicksum( x[k,t,j] for j in teams if j != t ) - 1 <= y[t,i,t] )

# (1g)
for t,j in arcs:
  model.addConstr( x[0,j,t] <= y[t,t,j] )

# (1h)
for i,t in arcs:
  model.addConstr( x[m-1,i,t] <= y[t,i,t] )

# non-repeater (12a)
if nonRepeater:
  for k,i,j in matches:
    if k != m-1:
      model.addConstr( x[k,i,j] + x[k+1,j,i] <= 1 )

# maximum consecutive home (12b)
if maxConsecutiveHome > 0:
  for k in slots:
    if k+maxConsecutiveHome < m:
      for t in teams:
        model.addConstr( quicksum( x[l,t,j] for l in range(k,k+maxConsecutiveHome+1) for j in teams if j != t ) <= maxConsecutiveHome, f'12b#{k}#{teamNames[t]}')

# maximum consecutive away (12c)
if maxConsecutiveAway > 0:
  for k in slots:
    if k+maxConsecutiveAway < m:
      for t in teams:
        model.addConstr( quicksum( x[l,i,t] for l in range(k,k+maxConsecutiveHome+1) for i in teams if i != t ) <= maxConsecutiveAway )

# Mirrored:
if mirrored:
  for k,i,j in matches:
    if k < m/2:
      model.addConstr( x[k,i,j] == x[k+m/2,j,i] )

# Flow inequalities (8)
if addFlow:
  for i,t in arcs:
    model.addConstr( quicksum( y[t,i,j] for j in teams if j != i ) >= 1 )
    model.addConstr( quicksum( y[t,j,i] for j in teams if j != i ) >= 1 )

# Flow equations (10)
if addFlowEquations:
  for i,t in arcs:
    model.addConstr( quicksum( y[t,i,j] for j in teams if j != i ) == 1 )
    model.addConstr( quicksum( y[t,j,i] for j in teams if j != i ) == 1 )

# Flow inequalities (8) for i=t (no facets)
if addFlowHome:
  for t in teams:
    model.addConstr( quicksum( y[t,t,j] for j in teams if j != t ) >= 1 )
    model.addConstr( quicksum( y[t,j,t] for j in teams if j != t ) >= 1 )

# Home fow inequalities (9)
if addHomeFlow:
  for k in slots:
    if k < m/2:
      for t in teams:
        model.addConstr( quicksum( y[t,t,j] for j in teams if j != t ) + quicksum( x[k,t,j] + x[k+m/2,t,j] for j in teams if j != t ) >= 2 )
        model.addConstr( quicksum( y[t,t,j] for j in teams if j != t ) + quicksum( x[k,j,t] + x[k+m/2,j,t] for j in teams if j != t ) >= 2 )
        model.addConstr( quicksum( y[t,i,t] for i in teams if i != t ) + quicksum( x[k,t,i] + x[k+m/2,t,i] for i in teams if i != t ) >= 2 )
        model.addConstr( quicksum( y[t,i,t] for i in teams if i != t ) + quicksum( x[k,i,t] + x[k+m/2,i,t] for i in teams if i != t ) >= 2 )

# Lifted versions of (1d): (5a) and (5b)
if addLiftedQuadDiff:
  for k in slots:
    if k != m-1:
      for i,j in arcs:
        for t in teams:
          if t != i and t != j:
            model.addConstr( x[k,j,t] + x[k,i,t] + x[k+1,j,t] - 1 <= y[t,i,j] )
            model.addConstr( x[k+1,i,t] + x[k,i,t] + x[k+1,j,t] - 1 <= y[t,i,j] )

# Lifted versions of (1e) and (1f): (6) and (7)
if addLiftedQuadSame:
  for k in slots:
    if k != m-1:
      for t,j in arcs:
        model.addConstr( x[0,j,t] + x[k,j,t] + quicksum( x[k,t,i] for i in teams if i != t ) + x[k+1,j,t] - 1 <= y[t,t,j] )
        pass
    if k != 0:
      for i,t in arcs:
        model.addConstr( x[m-1,i,t] + x[k,i,t] + x[k-1,i,t] + quicksum( x[k,t,j] for j in teams if j != t ) - 1 <= y[t,i,t] )

# Translated home-flow inequalities (14)
if addTranslatedHomeFlow:
  if maxConsecutiveHome > 0:
    for t in teams:
      model.addConstr( quicksum( y[t,t,j] for j in teams if j != t ) >= math.ceil((n-1) / maxConsecutiveHome), f'10a#{teamNames[t]}')
      model.addConstr( quicksum( y[t,i,t] for i in teams if i != t ) >= math.ceil((n-1) / maxConsecutiveHome), f'10b#{teamNames[t]}' )

model.optimize()

if model.status != GRB.INFEASIBLE:
  varTypeString = 'IP' if varType == GRB.BINARY else 'LP'
  upperBound = 1.0e99 if float(model.objVal) == float('inf') else model.objVal
  resultFile = open(f'{instanceName}.result', 'a')
  resultFile.write(f'{instanceName} {1 if addFlow else 0} {1 if addFlowEquations else 0} {1 if addFlowHome else 0} {1 if addHomeFlow else 0} {1 if addLiftedQuadDiff else 0} {1 if addLiftedQuadSame else 0} {1 if addTranslatedHomeFlow else 0} {varTypeString} {model.runtime} {model.objBound} {upperBound} {int(model.nodeCount)}\n')
  resultFile.close()

  if False:
    for k,i,j in matches:
      if x[k,i,j].x > 0.5:
        print(f'In slot {k}, team {teamNames[i]} plays home vs. team {teamNames[j]}.')
    totalDistance = 0.0
    for t in teams:
      for i,j, in arcs:
        if y[t,i,j].x > 0.5:
          print(f'Team {teamNames[t]} has to travel {teamNames[i]}->{teamNames[j]} with distance {distances[i,j]}.')
          totalDistance += distances[i,j]
    print(f'Total distance is {totalDistance}.')
