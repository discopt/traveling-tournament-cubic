import sys
import os

instanceFiles = sys.argv[1:]
for instanceFile in instanceFiles:
  print(instanceFile)
  for add567 in ['', '5 67 ']:
    for add8910 in ['', '8 8+ ', '8 9 ', '10 ', '10 8+ ', '9 10 ']:
      for add14 in ['', '14 ']:
        for prob in ['lp ', 'ip ']:
          params = prob + add567 + add8910 + add14
          call = f'python mip.py {instanceFile} {params}'
          os.system(call)
