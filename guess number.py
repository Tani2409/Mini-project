import random
num = random.randint(1,10)
guess = int(input("Guess a number between 1 and 10: "))
while guess != num:
    if guess < num:
        print("Too low!")
        guess = int(input("Guess again: "))
    elif guess > num:
        print("Too high!")
        guess = int(input("Guess again: "))
    else:
        break
print("Congratulations! You guessed it!")