# print(self.gauge())
# print(self.next_window_low(), self.next_window_high())

while True:
  if self.next_window_low() <= self.gauge() <= self.next_window_high():
    self.sync()