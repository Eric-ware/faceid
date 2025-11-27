import random,time
#A rock paper scissor game between user and computer
while True:
    a = 3
    while a > 0:
        print (a)
        time.sleep(1)
        a-=1
    b= str(input('rock,paper,scissors?:'))
    guess = 'rock','paper','scissors'
    x = random.choice(guess)
    if b==x:
        print("It's a tie ! computer chose", x)
    elif (b== 'scissors' and x=='rock') or (b== 'paper' and x=='scissors') or (b=='rock' and x=='paper'):
        print('You lose 🥺, computer chose',x)
    elif (b=='rock' and x=='scissors') or (b=='scissors' and x== 'paper') or (b== 'paper' and x== 'rock'):
        print( 'You won🥳, computter chose', x)
    c = str (input('Do you want to play again?,(yes/no)'))
    if c=='no':
        print ('ok')
        break
     
