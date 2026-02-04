import time

class PIDController:
    def __init__(self, kp, ki, kd, output_limits=(-100, 100)):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.min_out, self.max_out = output_limits
        
        self.prev_error = 0
        self.integral = 0
        self.last_time = None

    def update(self, error):
        current_time = time.time()
        
        if self.last_time is None:
            self.last_time = current_time
            dt = 0.0
        else:
            dt = current_time - self.last_time
            
        self.last_time = current_time

        p_term = self.kp * error
        self.integral += error * dt
        i_term = self.ki * self.integral

        d_term = 0
        if dt > 0:
            d_term = self.kd * (error - self.prev_error) / dt
        
        self.prev_error = error
        output = p_term + i_term + d_term
        return max(min(output, self.max_out), self.min_out)

    def reset(self):
        self.prev_error = 0
        self.integral = 0
        self.last_time = None
