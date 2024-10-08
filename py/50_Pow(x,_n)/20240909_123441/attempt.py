class Solution:
    def myPow(self, x: float, n: int) -> float:
        if x == 0:
            return 0
        if n == 0:
            return 1
        if n < 0:
            x = 1 / x
            n = -n
        result = 1
        while n > 0:
            if n & 1:
                result *= x
            x *= x
            n >>= 1
        return result

