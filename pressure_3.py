while True:
  if self.next_window_low() <= self.gauge() <= self.next_window_high():
    self.sync()