from typing import List


class Solution:
    def moveZeroes(self, nums: List[int]) -> None:
        """
        Do not return anything, modify nums in-place instead.
        """
        zero_pos = 0
        for i in range(len(nums)):
            if nums[i] != 0:
                if i != zero_pos:
                    nums[i], nums[zero_pos] = nums[zero_pos], nums[i]
                zero_pos += 1

