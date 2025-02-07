from modules.utils import get_diffraction_center, monitor_to_array
from uedinst.dectris import Quadro
from . import IP, PORT 
import matplotlib.pylab as plt
q = Quadro(
    IP,
    PORT
)

print(q)
try:
    _ = q.state
    connected = True
    print(f"DectrisImageGrabber successfully connected to detector\n{q}")
except OSError:
    print("DectrisImageGrabber could not establish connection to detector")

# prepare the hardware for taking images
if q.state == "na":
    print('Dectris not initialized.')

q.mon.clear()
q.fw.clear()
q.fw.mode = "disabled"
q.mon.mode = "enabled"
q.incident_energy = 1e5
q.count_time = 1
q.frame_time = 1
q.trigger_mode = 'ints'
q.ntrigger = 1

def get_dectris_image():
    q.ntrigger = 1
    q.arm()
    # logic for different trigger modes
    if q.trigger_mode == "ints":
        q.trigger()
        q.disarm()
    dectris_img = monitor_to_array(q.mon.last_image)
    q.mon.clear()
    return dectris_img

for idn in range(1):
    for i, m_channel in enumerate(range(2)):
        image1 = get_dectris_image()
        print(image1)
        image2 = get_dectris_image()
        print(image2)



del(q)

plt.imshow(image1)
plt.show()

plt.pause(10)