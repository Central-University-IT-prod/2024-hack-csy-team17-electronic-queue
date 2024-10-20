import qrcode

data = "https://www.queue.com"

qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=10,
    border=4,
)

qr.add_data(data)
qr.make(fit=True)

img = qr.make_image(fill='black', back_color='white')

img.save("static/{queue_point_id}_qr_code.png")


queue_point_id =2
f"static/{queue_point_id}_qr_code.png"
