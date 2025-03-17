# install in prompt pip install discord.py==1.7.3
import discord
from discord.ext import commands

   # Configura el bot (reemplaza 'TOKEN' con tu token de usuario)
# TOKEN = "MTMzMTYyODIwNjg0Mjk3NDI4Mw.GzUevB.QCD2qKhjn5_3ZccME4QCPrKhCVcVk2ae0sAfxc"
TOKEN = "MzY1NjkxMDg2NTE1MDc3MTIw.GzBzUH.Spwoouj3IRUVffcblY-h0BmIsIA90TfGGDYCrs"
intents = discord.Intents.default()
intents.messages = True  # Habilita la recepción de mensajes  


client = commands.Bot(command_prefix="r", self_bot=True, intents=intents)

message=""   
    
@client.event
async def on_ready():
    print('hola como va todo')   
    
@client.event
async def on_message(message):
    print(f"Contenido: {message.content}\n")      # imprime los mensajes que llegan al chat 
    msj_leido = message.content
    print(msj_leido)
    
# inicia el self_bot    
client.run(TOKEN, bot=False)   


  


       


   
