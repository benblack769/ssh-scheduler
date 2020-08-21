import numpy as np
import timeit
import numexpr as ne
a = np.random.uniform(size=1000000)
b = np.random.uniform(size=1000000)
c,d = ne.evaluate("2*cos(a), 3*sin(b)")

# time = timeit.timeit('2*np.cos(a) + 3*np.sin(b)', setup="import numexpr as ne;import numpy as np;a = np.random.uniform(size=1000000);b = np.random.uniform(size=1000000)", number=100)
# print(time)
