import sys, random, argparse
import numpy as np
import math
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw 
from PIL import Image
 
# gray scale level values from:
# http://paulbourke.net/dataformats/asciiart/
 
# 70 levels of gray
gscale1 = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
 
# 10 levels of gray
gscale2 = '@%#*+=-:. '


def chars_to_nums(img:np.array):
  chars = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "  
  chardict = {}
  for v,k in enumerate(chars):
    chardict[k] = v

  return np.vectorize(chardict.get)(img)


def ascii_to_num(img):
  for i in range(len(img)):
    img[i] = list(img[i])
  img = np.array(img)
  style_img = np.expand_dims(img, -1)
  # convert ascii back to number
  style_img = chars_to_nums(style_img)
  return style_img


class Config:
    imgFile = "texture.jpeg"
    outFile = "tex_ascii.png"
    scale = 1
    cols = 80
    moreLevels = True
 

def image_to_ascii(image, cols=80, scale=1)->list:
    """
    Given Image and dims (rows, cols) returns an m*n list of Images
    """ 
    # store dimensions
    W, H = image.size[0], image.size[1]
    print("input image dims: %d x %d" % (W, H))
 
    # compute width of tile
    w = W/cols
 
    # compute tile height based on aspect ratio and scale
    h = w/scale
 
    # compute number of rows
    rows = int(H/h)
     
    print("cols: %d, rows: %d" % (cols, rows))
    print("tile dims: %d x %d" % (w, h))
 
    # check if image size is too small
    if cols > W or rows > H:
        print("Image too small for specified cols!")
        exit(0)
 
    # ascii image is a list of character strings
    aimg = []
    # generate list of dimensions
    for j in range(rows):
        y1 = int(j*h)
        y2 = int((j+1)*h)
 
        # correct last tile
        if j == rows-1:
            y2 = H
 
        # append an empty string
        aimg.append("")
 
        for i in range(cols):
 
            # crop image to tile
            x1 = int(i*w)
            x2 = int((i+1)*w)
 
            # correct last tile
            if i == cols-1:
                x2 = W
            # crop image to extract tile
            img = image.crop((x1, y1, x2, y2))
            # get average luminance
            avg = int(np.average(np.array(img)))
            # look up ascii char
            gsval = gscale1[int((avg*69)/255)]
            # append ascii char to string
            aimg[j] += gsval
     
    # return txt image
    return aimg


def draw_ascii(aimg:list, config):

    img = Image.new('RGB', (config.cols*9, config.cols*9))
    draw = ImageDraw.Draw(img)
    # font = ImageFont.truetype("arial.ttf", 16)
    for i, row in enumerate(aimg):
    # print(row)
        draw.text(xy=(0, 8 * i), text=row, fill=(255,0,0), spacing=50.3) # ,font=font
    img.show()
    img.save(config.outFile)
    

def main():
    # create pa
    # add expected arguments
  
    image = Image.open(Config.imgFile).convert('L')
    print('generating ASCII art...')     
    aimg = image_to_ascii(image, Config.cols, Config.scale)
    
    print(aimg)   

    draw_ascii(aimg, Config)
 
# call main
if __name__ == '__main__':
    main()