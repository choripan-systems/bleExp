# bleExp

**bleExp** is a simple Bluetooth Low Energy explorer app. It lets the user discover BLE devices that advertise the specified service UUID, connect to them, and list all its services, characteristics, and descriptors.  The app automatically reads the value of all the readable characteristics, and lets the user write an arbitrary value to any of the writeable characteristics. The app also lets the user enable or disable notifications/indications on any charactersitic that supports them, and the notifications/indications received from the BLE device are shown on the app's output log.

The image below shows the **bleExp** app connected to a Wahoo TICKR Heart Rate sensor:

![bleExp app connected to a Wahoo TICKR HRM device](./assets/bleExp-Wahoo-TICKR.png)
