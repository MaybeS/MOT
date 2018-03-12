from urllib import request
from pathlib import Path
from zipfile import ZipFile
from os import remove

prefix = 'http://cvlab.hanyang.ac.kr/tracker_benchmark/'
targets = ['seq/Basketball.zip', 'seq/Biker.zip', 'seq/Bird1.zip', 'seq/BlurBody.zip', 'seq/BlurCar2.zip', 'seq/BlurFace.zip', 'seq/BlurOwl.zip', 'seq/Bolt.zip', 'seq/Box.zip', 'seq/Car1.zip', 'seq/Car4.zip', 'seq/CarDark.zip', 'seq/CarScale.zip', 'seq/ClifBar.zip', 'seq/Couple.zip', 'seq/Crowds.zip', 'seq/David.zip', 'seq/Deer.zip', 'seq/Diving.zip', 'seq/DragonBaby.zip', 'seq/Dudek.zip', 'seq/Football.zip', 'seq/Freeman4.zip', 'seq/Girl.zip', 'seq/Human3.zip', 'seq/Human4.zip', 'seq/Human6.zip', 'seq/Human9.zip', 'seq/Ironman.zip', 'seq/Jump.zip', 'seq/Jumping.zip', 'seq/Liquor.zip', 'seq/Matrix.zip', 'seq/MotorRolling.zip', 'seq/Panda.zip', 'seq/RedTeam.zip', 'seq/Shaking.zip', 'seq/Singer2.zip', 'seq/Skating1.zip', 'seq/Skating2.zip', 'seq/Skiing.zip', 'seq/Soccer.zip', 'seq/Surfer.zip', 'seq/Sylvester.zip', 'seq/Tiger2.zip', 'seq/Trellis.zip', 'seq/Walking.zip', 'seq/Walking2.zip', 'seq/Woman.zip', 'seq/Bird2.zip', 'seq/BlurCar1.zip', 'seq/BlurCar3.zip', 'seq/BlurCar4.zip', 'seq/Board.zip', 'seq/Bolt2.zip', 'seq/Boy.zip', 'seq/Car2.zip', 'seq/Car24.zip', 'seq/Coke.zip', 'seq/Coupon.zip', 'seq/Crossing.zip', 'seq/Dancer.zip', 'seq/Dancer2.zip', 'seq/David2.zip', 'seq/David3.zip', 'seq/Dog.zip', 'seq/Dog1.zip', 'seq/Doll.zip', 'seq/FaceOcc1.zip', 'seq/FaceOcc2.zip', 'seq/Fish.zip', 'seq/FleetFace.zip', 'seq/Football1.zip', 'seq/Freeman1.zip', 'seq/Freeman3.zip', 'seq/Girl2.zip', 'seq/Gym.zip', 'seq/Human2.zip', 'seq/Human5.zip', 'seq/Human7.zip', 'seq/Human8.zip', 'seq/Jogging.zip', 'seq/KiteSurf.zip', 'seq/Lemming.zip', 'seq/Man.zip', 'seq/Mhyang.zip', 'seq/MountainBike.zip', 'seq/Rubik.zip', 'seq/Singer1.zip', 'seq/Skater.zip', 'seq/Skater2.zip', 'seq/Subway.zip', 'seq/Suv.zip', 'seq/Tiger1.zip', 'seq/Toy.zip', 'seq/Trans.zip', 'seq/Twinnings.zip', 'seq/Vase.zip']

objs = []
for tar in targets:
    objs.append(Path(tar).stem)
    path = Path("./train/") / Path(tar).name
    print ('Download', str(path))
    request.urlretrieve(prefix + tar, str(path))
    print ('Extract', str(path))
    zip = ZipFile(str(path), 'r')
    zip.extractall("./train")
    zip.close()
    remove(str(path))
    print (str(path), 'done!')

with open('labels.txt', 'w') as f:
    f.write('\n'.join(objs))

