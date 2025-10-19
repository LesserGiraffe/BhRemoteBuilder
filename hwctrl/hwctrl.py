from typing import Final, Sequence
from types import TracebackType
from typing_extensions import Self
from collections.abc import Callable
from queue import SimpleQueue, Empty
from concurrent.futures import ThreadPoolExecutor, Future
from enum import auto, StrEnum
from gpiozero import LED, PWMOutputDevice, OutputDevice
from time import sleep
import sys
import threading
import signal
import smbus2
import gpiozero.pins.lgpio

# プログラム終了フラグ
is_terminated = False

class Opcode(StrEnum):
    MOVE: Final = 'move'
    MEASURE_DISTANCE: Final = 'measure-distance'
    DETECT_COLOR: Final = 'detect-color'
    LIGHT_EYE: Final = 'light-eye'


class RaspiCarMoveOp(StrEnum):
    """RaspiCar が実行可能な移動の種類"""
    FORWARD: Final = 'fwd'
    BACKWARD: Final = 'bwd'
    CLOCKWISE: Final = 'cw'
    COUNTERCLOCKWISE: Final = 'ccw'
    STOP: Final = 'stop'

class RaspiCarEye(StrEnum):
    """RaspiCar の目の識別子"""
    LEFT: Final = 'left',
    RIGHT: Final = 'right',
    BOTH: Final = 'both'

class HwCtrlCmd:

    @classmethod
    def of(cls, cmd: str):
        fields = cmd.split(',')
        num_fields = len(fields)
        cmd_no = fields[0] if num_fields >= 1 else ''
        opcode = fields[1] if num_fields >= 2 else ''
        params = fields[2:] if num_fields >= 3 else []
        return HwCtrlCmd(cmd_no, opcode, params)

    def __init__(
        self,
        cmd_no: str,
        opcode: str,
        params: list[str] = []
    ) -> None:
        """HW 制御コマンド"""
        self.__cmd_no = cmd_no
        self.__opcode = opcode
        self.__params = params

    @property
    def cmd_no(self) -> str:
        return self.__cmd_no

    @property
    def opcode(self) -> str:
        return self.__opcode

    @property
    def params(self) -> list[str]:
        return self.__params


class HwCtrlResp:

    def __init__(
        self,
        cmd_no: str,
        opcode: str,
        success: bool,
        data: list[str] = []
    ) -> None:
        """HW 制御コマンドの応答データ"""
        self.__cmd_no = cmd_no
        self.__opcode = opcode
        self.__success = success
        self.__data = data
    
    @property
    def cmd_no(self) -> str:
        return self.__cmd_no
    
    @property
    def opcode(self) -> str:
        return self.__opcode

    @property
    def is_successful(self) -> bool:
        return self.__success
    
    @property
    def data(self) -> list[str]:
        return self.__data

    def __str__(self):
        res = f'{self.cmd_no},{self.is_successful},{self.opcode}'
        for val in self.data:
           res += ',' + val
        return res


class MoveCtrl:
    def __init__(self) -> None:
        self.__pwm = PWMOutputDevice(12)
        self.__lhs_phase = OutputDevice(16)
        self.__rhs_phase = OutputDevice(26)

    def move(self, move_op: RaspiCarMoveOp, speed: float) -> None:
        """モータを制御する"""
        if move_op == RaspiCarMoveOp.FORWARD:
            self.forward(speed)
        elif move_op == RaspiCarMoveOp.BACKWARD:
            self.backward(speed)
        elif move_op == RaspiCarMoveOp.CLOCKWISE:
            self.clockwise(speed)
        elif move_op == RaspiCarMoveOp.COUNTERCLOCKWISE:
            self.counter_clockwise(speed)
        elif move_op == RaspiCarMoveOp.STOP:
            self.stop()

    def forward(self, speed: float) -> None:
        speed = min(1, max(speed, 0))
        self.__lhs_phase.off()
        self.__rhs_phase.off()
        self.__pwm.value = speed

    def backward(self, speed: float) -> None:
        speed = min(1, max(speed, 0))
        self.__lhs_phase.on()
        self.__rhs_phase.on()
        self.__pwm.value = speed

    def clockwise(self, speed: float) -> None:
        speed = min(1, max(speed, 0))
        self.__lhs_phase.off()
        self.__rhs_phase.on()
        self.__pwm.value = speed

    def counter_clockwise(self, speed: float) -> None:
        speed = min(1, max(speed, 0))
        self.__lhs_phase.on()
        self.__rhs_phase.off()
        self.__pwm.value = speed

    def stop(self) -> None:
        self.__pwm.value = 0


class CmdProcessor:
    __COLOR_SENSOR_I2C_ADDR = 0x2A
    __DISTANCE_SENSOR_I2C_ADDR = 0x57

    def __init__(self) -> None:
        self.__i2c1 = smbus2.SMBus(1)
        self.__i2c_lock = threading.Lock()
        self.__color_sensor_lock = threading.Lock()
        self.__move_lock = threading.Lock()
        self.__num_times_moved = 0
        self.__move_event: threading.Event | None = None
        self.__get_color_event: threading.Event | None = None
        self.__activeCmds: set[HwCtrlCmd] = set()
        self.__move_ctrl = MoveCtrl()
        self.__right_eye = {
            'red':   LED(23),
            'green': LED(25),
            'blue':  LED(24)
        }
        self.__left_eye = {
            'red':   LED(17),
            'green': LED(22),
            'blue':  LED(27)
        }

    def process(self, cmd: HwCtrlCmd) -> HwCtrlResp:
        """引数で与えられたコマンドを処理して, その応答を返す."""
        try:
            self.__activeCmds.add(cmd)
            if cmd.opcode == Opcode.DETECT_COLOR:
                return self.__detect_color(cmd)
            elif cmd.opcode == Opcode.MOVE:
                return self.__move(cmd)
            elif cmd.opcode == Opcode.MEASURE_DISTANCE:
                return self.__measure_distance(cmd)
            elif cmd.opcode == Opcode.LIGHT_EYE:
                return self.__light_eye(cmd)
        finally:
            self.__activeCmds.remove(cmd)
        
        return HwCtrlResp(cmd.cmd_no, cmd.opcode, False)

    def __detect_color(self, cmd: HwCtrlCmd) -> HwCtrlResp:
        """色を取得するコマンドを処理する"""
        try:
            self.__color_sensor_lock.acquire()
            colors = self.__get_color_sensor_val(float(cmd.params[0]))
            if colors:
                resp_data = [str(color) for color in colors]
                return HwCtrlResp(cmd.cmd_no, cmd.opcode, True, resp_data)
            else:
                return HwCtrlResp(cmd.cmd_no, cmd.opcode, False)
        except Exception as e:
            return HwCtrlResp(cmd.cmd_no, cmd.opcode, False)
        finally:
            self.__color_sensor_lock.release()

    def __get_color_sensor_val(self, exp_time: float) -> list[int]:
        """カラーセンサー (S11059-02DT) 使って色を取得する

        :param exposure_time: センサのフォトダイオード 1 色分の露光時間. 有効な値は 0 ~ 11. (単位: 秒)
        :return: [red, green, blue] の順に並んだ各色の値のリスト.  色の取得に失敗した場合は空のリスト.
        """
        max_exp_time = 11 # sec
        exp_time_us = max(0, min(exp_time, max_exp_time)) * 1e6 # us
        exp_unit_time = 175 # us
        integ_val = int(exp_time_us / exp_unit_time) # 積分時間マニュアル設定レジスタの値
        event = threading.Event()
        try:
            self.__i2c_lock.acquire()
            self.__i2c1.write_byte_data(self.__COLOR_SENSOR_I2C_ADDR, 0, 0b10001100)
            self.__i2c1.write_byte_data(self.__COLOR_SENSOR_I2C_ADDR, 1, integ_val >> 8)
            self.__i2c1.write_byte_data(self.__COLOR_SENSOR_I2C_ADDR, 2, integ_val & 0xFF)
            self.__i2c1.write_byte_data(self.__COLOR_SENSOR_I2C_ADDR, 0, 0b00001100)
            self.__get_color_event = event
        except Exception as e:
            return []
        finally:
            self.__i2c_lock.release()
        
        event.wait((4 * exp_time) * 1.05) # red, green, blue, infrared の露光時間分待つ

        try:
            self.__i2c_lock.acquire()
            color_vals = self.__i2c1.read_i2c_block_data(self.__COLOR_SENSOR_I2C_ADDR, 3, 8)
        except Exception as e:
            return []
        finally:
            self.__i2c_lock.release()

        return [
            color_vals[0] << 8 | color_vals[1],
            color_vals[2] << 8 | color_vals[3],
            color_vals[4] << 8 | color_vals[5]]

    def __cancel_color_detection(self) -> None:
        """色の取得をキャンセルする"""
        if self.__get_color_event is not None:
            self.__get_color_event.set()

    def __move(self, cmd: HwCtrlCmd) -> HwCtrlResp:
        """移動コマンドを処理する"""
        success = False
        try:
            move_op = RaspiCarMoveOp(cmd.params[0])
            if move_op == RaspiCarMoveOp.STOP:
                success = self.__stop_raspicar()
            else:
                speed = float(cmd.params[1])
                time = float(cmd.params[2])
                success = self.__move_raspicar(move_op, speed, time)
        except Exception as e:
            pass
        
        return HwCtrlResp(cmd.cmd_no, cmd.opcode, success)

    def __move_raspicar(self, move_op: RaspiCarMoveOp, speed: float, time: float) -> bool:
        """RaspiCar を移動させる.

        :param move_op: RaspiCar の移動動作
        :param speed: RaspiCar の移動速度 (0 ~ 1)
        :param time: RaspiCar の移動時間 (sec).  この時間が経過した後, RaspiCar は止まる.
        :return: True -> 成功, False -> 失敗
        """
        event = threading.Event()
        try:
            self.__move_lock.acquire()
            self.__num_times_moved += 1
            num_times_moved = self.__num_times_moved
            self.__move_ctrl.move(move_op, speed)
            self.__cancel_move()
            self.__move_event = event
        except Exception as e:
            return False
        finally:
            self.__move_lock.release()

        event.wait(time)

        try:
            self.__move_lock.acquire()
            # wait 中に別の移動コマンドがあった場合, 停止処理は行わない.
            if num_times_moved != self.__num_times_moved:
                return True
            self.__move_ctrl.stop()
        except Exception as e:
            return False
        finally:
            self.__move_lock.release()

        return True
    
    def __stop_raspicar(self) -> bool:
        """RaspiCar を停止させる.
        
        :return: True: 成功, False: 失敗
        """
        try:
            self.__move_lock.acquire()
            self.__num_times_moved += 1
            self.__move_ctrl.stop()
            self.__cancel_move()
        except Exception as e:
            return False
        finally:
            self.__move_lock.release()
        return True

    def __cancel_move(self) -> None:
        """RaspiCar の移動をキャンセルする"""
        if self.__move_event is not None:
            self.__move_event.set()

    def __measure_distance(self, cmd: HwCtrlCmd) -> HwCtrlResp:
        """HCSR-04 を使って距離を測定する."""
        try:
            self.__i2c_lock.acquire()
            self.__i2c1.write_byte(self.__DISTANCE_SENSOR_I2C_ADDR, 0x1)
            sleep(0.2)
            data = self.__i2c1.read_i2c_block_data(self.__DISTANCE_SENSOR_I2C_ADDR, 0, 3)
            distance = (data[0] << 16 | data[1] << 8 | data[2])  # um
            return HwCtrlResp(cmd.cmd_no, cmd.opcode, True, [str(distance)])
        except Exception as e:
            return HwCtrlResp(cmd.cmd_no, cmd.opcode, False)
        finally:
            self.__i2c_lock.release()

    def __light_eye(self, cmd: HwCtrlCmd) -> HwCtrlResp:
        """RaspiCar の目を光らせる."""
        try:
            eye = cmd.params[0]
            red = bool(int(cmd.params[1]))
            green = bool(int(cmd.params[2]))
            blue = bool(int(cmd.params[3]))
            if eye == RaspiCarEye.LEFT or eye == RaspiCarEye.BOTH:
                self.__light_leds({
                    self.__left_eye['red']:   red,
                    self.__left_eye['green']: green,
                    self.__left_eye['blue']:  blue
                })
            if eye == RaspiCarEye.RIGHT or eye == RaspiCarEye.BOTH:
                self.__light_leds({
                    self.__right_eye['red']:   red,
                    self.__right_eye['green']: green,
                    self.__right_eye['blue']:  blue
                })
            return HwCtrlResp(cmd.cmd_no, cmd.opcode, True)
        except Exception as e:
            return HwCtrlResp(cmd.cmd_no, cmd.opcode, False)
    
    @classmethod
    def __light_leds(cls, led_to_flag: dict[LED, bool]) -> None:
        for led, flag in led_to_flag.items():
            if flag:

                led.on()
            else:
                led.off()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None
    ) -> None:
        self.close()

    def close(self) -> None:
        """このプロセッサと関連付けられたすべてのリソースを開放する.

        | このクラスのインスタンスを with 構文による後処理の対象にした場合, このメソッドを明示的に呼ぶ必要はない.
        | そうでない場合, プログラムを終了する前にこのメソッドを呼ぶこと.

        """
        count = 0
        while len(self.__activeCmds) != 0 and count < 15:
            count += 1
            self.__cancel_move()
            self.__cancel_color_detection()
            sleep(0.1)
        for led in list(self.__right_eye.values()) + list(self.__right_eye.values()):
            led.off()

        self.__i2c1.close()

def on_killed(signum, frame) -> None:
    sys.exit(1)

def close(processor: CmdProcessor, futures: Sequence[Future]) -> None:
    """プログラムの終了処理を行う"""
    # スレッド停止
    global is_terminated
    is_terminated = True
    # HW のクロージング
    processor.close()
    # スレッド停止待ち
    for future in futures:
        future.result()

def output_fifo_elems(fifo: SimpleQueue[HwCtrlResp]) -> None:
    """FIFO の要素を標準出力に出力し続ける"""
    while not is_terminated:
        try:
            resp = str(fifo.get(timeout = 0.1))
            sys.stdout.write(resp + '\n')
            sys.stdout.flush()
        except Empty:
            pass

def process_cmds(
    processor: CmdProcessor,
    cmd_fifo: SimpleQueue[HwCtrlCmd],
    resp_fifo: SimpleQueue[HwCtrlResp]) -> None:
    """コマンドを処理し続ける."""
    while not is_terminated:
        try:
            cmd = cmd_fifo.get(timeout = 0.1)
            resp = processor.process(cmd)
            resp_fifo.put(resp)
        except Empty:
            pass

def main():
    num_workers = 6
    processor = CmdProcessor()
    signal.signal(signal.SIGTERM, on_killed)
    futures = []
    with (ThreadPoolExecutor(max_workers=num_workers) as executor):
        try:
            cmd_fifo = SimpleQueue()
            resp_fifo = SimpleQueue()
            futures = [
                executor.submit(process_cmds, processor, cmd_fifo, resp_fifo)
                for _ in range(num_workers - 1) ]
            futures.append(executor.submit(output_fifo_elems, resp_fifo))
            for line in sys.stdin:
                data = line.rstrip('\n')
                if data == 'terminate':
                    break
                cmd_fifo.put(HwCtrlCmd.of(data))
        finally:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            close(processor, futures)
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            signal.signal(signal.SIGINT, signal.SIG_DFL)

    return 0

if __name__ == '__main__':
    sys.exit(main())
