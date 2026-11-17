using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Windows.Forms;

class GateShot
{
    static void Main()
    {
        Rectangle b = Screen.PrimaryScreen.Bounds;
        using (Bitmap bmp = new Bitmap(b.Width, b.Height, PixelFormat.Format32bppArgb))
        {
            using (Graphics g = Graphics.FromImage(bmp))
            {
                g.CopyFromScreen(b.X, b.Y, 0, 0, b.Size);
            }
            bmp.Save(@"C:\Users\Public\shot.png", ImageFormat.Png);
        }
    }
}
