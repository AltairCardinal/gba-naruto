import sys
n = 8000000
total = 0
for i in range(n):
    total = (total + i * i) % 1000000007
print(total)
