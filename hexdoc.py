#!/usr/bin/env python3
import argparse
import math
import os
import random
import sys
from PIL import Image, ImageDraw, ImageFont

HexChars = "0123456789abcdef"

class HexDrawer:
    def __init__(self, font):
        self.setFont(font)
        self.byteGap = 5
        self.groupGap = 5
        self.bytesPerRow = 32
        self.color = (0, 0, 0, 255)
        self.fadeInRows = 0
        self.fadeOutRows = 0
        self.showAddress = True
        self.alignData = True
        self.groupSize = self.bytesPerRow


    def setFont(self, font):
        self.font = font
        self.charSizes = [font.getsize(c) for c in HexChars]
        self.charHeight = max(h for w, h in self.charSizes)
        self.charWidth = max(w for w, h in self.charSizes)

    def drawDigits(self, imgDraw, position, color, value, digits):
        x, y = position
        align = 1
        for i in range(digits):
            digit = (value >> (4 * (digits - i - 1))) & 0xF
            char = HexChars[digit]
            offset = (self.charWidth - self.charSizes[digit][0] + align) // 2
            imgDraw.text((x + offset, y), char, font=self.font, fill=color)
            align = 0
            x += self.charWidth


    def getFirstColumn(self, address):
        return address % self.bytesPerRow if self.alignData else 0


    def getAddressDigits(self, count, address):
        return int(math.ceil(math.log(address + count) / math.log(16)))


    def getAddressText(self, count, address):
        firstColumn = self.getFirstColumn(address)
        address = address + self.fadeInRows * self.bytesPerRow - firstColumn
        return "%0*x" % (self.getAddressDigits(count, address), address)


    def getAddressWidth(self, count, address):
        return len(self.getAddressText(count, address)) * self.charWidth


    def getSize(self, count, address=0):
        if self.showAddress:
            xOffset = self.getAddressWidth(count, address) + 10
        else:
            xOffset = 0
        width = xOffset + self.bytesPerRow * self.charWidth * 2
        width += (self.bytesPerRow - 1) * self.byteGap
        width += ((self.bytesPerRow - 1) // self.groupSize) * self.groupGap
        firstColumn = self.getFirstColumn(address)
        rows = (firstColumn + count + self.bytesPerRow - 1) // self.bytesPerRow
        height = rows * self.charHeight
        return width, height


    def __getGroupSeparators(self):
        return [(self.groupGap if (i + 1) % self.groupSize == 0 else 0)
                for i in range(self.bytesPerRow)]


    def draw(self, imgDraw, position, buffer, count, address=0):
        firstColumn = self.getFirstColumn(address)
        if self.showAddress:
            xOffset = self.getAddressWidth(count, address) + 10
        else:
            xOffset = 0

        separators = self.__getGroupSeparators()

        col = firstColumn
        x = position[0] + xOffset + col * (2 * self.charWidth + self.byteGap)
        y = position[1]
        i = 0
        rows = (firstColumn + count + self.bytesPerRow - 1) // self.bytesPerRow

        assert(rows >= self.fadeInRows + self.fadeOutRows)

        addressDigits = self.getAddressDigits(count, address)

        for row in range(self.fadeInRows):
            if (address + i) % 0x80 == 0:
                self.drawDigits(imgDraw, (position[0], y), self.color, address + i, addressDigits)
            alpha = (row + 1) * 255 // (self.fadeInRows + 1)
            color = *self.color[:-1], alpha
            for col in range(col, self.bytesPerRow):
                assert(0 <= buffer[i] <= 255)
                self.drawDigits(imgDraw, (x, y), color, buffer[i], 2)
                x += 2 * self.charWidth + self.byteGap + separators[col]
                i += 1
            x = position[0] + xOffset
            y += self.charHeight
            col = 0

        # addressText = self.getAddressText(count, address)
        self.drawDigits(imgDraw, (position[0], y), self.color, address + i, addressDigits)
        for row in range(self.fadeInRows, rows - self.fadeOutRows):
            if (address + i) % 0x80 == 0 and row != self.fadeInRows:
                self.drawDigits(imgDraw, (position[0], y), self.color, address + i, addressDigits)
            maxCol = min(self.bytesPerRow, col + count - i)
            for col in range(col, maxCol):
                assert(0 <= buffer[i] <= 255)
                self.drawDigits(imgDraw, (x, y), self.color, buffer[i], 2)
                x += 2 * self.charWidth + self.byteGap + separators[col]
                i += 1
            x = position[0] + xOffset
            y += self.charHeight
            col = 0

        for row in range(rows - self.fadeOutRows, rows):
            if (address + i) % 0x80 == 0:
                self.drawDigits(imgDraw, (position[0], y), self.color, address + i, addressDigits)
            alpha = (rows - row) * 255 // (self.fadeOutRows + 1)
            color = *self.color[:-1], alpha
            maxCol = min(self.bytesPerRow, col + count - i)
            for col in range(0, maxCol):
                assert(0 <= buffer[i] <= 255)
                self.drawDigits(imgDraw, (x, y), color, buffer[i], 2)
                x += 2 * self.charWidth + self.byteGap + separators[col]
                i += 1
            x = position[0] + xOffset
            y += self.charHeight
            col = 0


def parseSize(s):
    return [int(n) for n in s.lower().split("x", 1)]


def makeArgParser():
    ap = argparse.ArgumentParser(description='Creates a RGBA PNG file listing the bytes from some section of file as hexadecimal values.')
    ap.add_argument("data file", help="the file whose contents will be rendered")
    ap.add_argument("image file", nargs="?",
                    help="The file whose contents will be rendered.")
    ap.add_argument("-s", "--size", metavar="WIDTHxHEIGHT", type=parseSize,
                    default=[0, 0],
                    help="The image width and height in pixels.")
    ap.add_argument("-a", "--address", metavar="POS", default=0,
                    type=lambda s: int(s, 0),
                    help="The position of the first byte that will be rendered.")
    ap.add_argument("-n", "--number", metavar="N", default=1024,
                    type=lambda s: int(s, 0),
                    help="The number of bytes that will be rendered.")
    ap.add_argument("--columns", metavar="N", type=int, default=32,
                    help="The number of bytes per row.")
    ap.add_argument("--fadein", metavar="N", type=int, default=0,
                    help="The number of rows at the beginning that will be used to \"fade in\" the text.")
    ap.add_argument("--fadeout", metavar="N", type=int, default=0,
                    help="The number of rows at the end that will be used to \"fade out\" the text.")
    ap.add_argument("--fontsize", metavar="N", type=int, default=10,
                    help="Font size.")
    ap.add_argument("--font", metavar="FILE", default="",
                    help="The font that will be used.")
    ap.add_argument("--color", metavar="RRGGBB", default=0,
                    type=lambda s: int(s, 16),
                    help="Text color (hexadecimal).")
    return ap


def decodeColor(intValue):
    b = intValue & 0xFF
    intValue >>= 8
    g = intValue & 0xFF
    intValue >>= 8
    r = intValue & 0xFF
    return r, g, b, 0xFF


def readBytes(fileName, pos, count):
    file = open(fileName, "rb")
    if pos:
        pos = file.seek(pos, 0 if pos > 0 else 2)
    return pos, file.read(count)


def main():
    try:
        args = makeArgParser().parse_args()
    except argparse.ArgumentError as ex:
        print(ex)
        return 1
    argVars = vars(args)
    dataFile = argVars["data file"]
    path = os.path.dirname(sys.argv[0])
    fontFile = args.font if args.font else "xkcd-script.ttf"
    font = ImageFont.truetype(os.path.join(path, fontFile), args.fontsize)
    hexDrawer = HexDrawer(font)
    hexDrawer.color = decodeColor(args.color)
    hexDrawer.bytesPerRow = args.columns
    hexDrawer.fadeInRows = args.fadein
    hexDrawer.fadeOutRows = args.fadeout
    hexDrawer.groupSize = 4
    pos, buffer = readBytes(dataFile, args.address, args.number)
    print(hexDrawer.getSize(args.number, pos))
    width, height = args.size
    if width <= 0 or height <= 0:
        autoSize = hexDrawer.getSize(args.number, pos)
        if width <= 0:
            width = autoSize[0] + 4
        if height <= 0:
            height = autoSize[1] + 4
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    hexDrawer.draw(draw, (2, 2), buffer, args.number, pos)

    del draw
    imageFile = argVars["image file"]
    if not imageFile:
        imageFile = argVars["data file"] + ".png"
    img.save(imageFile, "PNG")


if __name__ == "__main__":
    sys.exit(main())
