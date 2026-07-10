# Transcript

language: en (p=1.00)

[00:00] Hi, and welcome back.
[00:02] This strategy uses reinforcement learning to train a trading AI agent on historical data.
[00:07] I have chosen the Eurya's Dollar hourly time frame for today's example.
[00:11] The model showed an increasing equity on learning data and acceptable learning rate.
[00:15] In other words, we're trying to make an AI model that reads historical data, applies
[00:20] trading operations and learns from winning and losing trades in order to come up with
[00:24] the best trading pattern, pretty much like a human would learn trading.
[00:28] You can download the Python code used in this video from the link in the description.
[00:32] Feel free to explore the files and use them in your own experiments.
[00:36] But first, let's summarize briefly how reinforcement learning works.
[00:40] Reinforcement learning relies on five main concepts.
[00:42] The agent, in this case, it's the one or the model making trading decisions, putting
[00:46] long and short positions and setting stop loss and take profit distances.
[00:50] The environment where the agent operates, the action or the actions that can be taken
[00:56] by the agent, then depending on the result of an action, the agent receives a reward
[01:01] that can be either positive or negative with different values.
[01:05] One more concept is the policy, which is the agent's strategy or mapping from
[01:09] different states of the environment to actions.
[01:12] In other words, it's the decision patterns learned so far by the agent,
[01:17] considering the current environment state.
[01:19] If you are familiar with reinforcement learning, this would be a model-free
[01:23] approach where the agent learns directly from experience or trial and error in the environment.
[01:29] Think about it as training a dog to complete certain tasks.
[01:33] Every time the dog does well, it will receive a reward.
[01:36] And if it doesn't, then either the reward is null or it can be also negative.
[01:40] Of course, AI agents don't have this intrinsic motivation for the reward.
[01:45] So they can be coded in a way to maximize the reward value.
[01:49] In other words, if the agent receives more reward doing action A,
[01:53] then this action will be attributed the highest probability in the future.
[01:58] So now we will define our environment, the agent and the list of possible actions
[02:02] that the agent will use to trade in the created environment.
[02:05] And we will let the agent run trading on historical data for around 10 years,
[02:10] for example, and learning from the reward system the best possible ways of trading.
[02:16] Just like a human trader learning new strategies and experimenting with trial
[02:20] and error to improve his trading skills.
[02:22] Okay, now let's see how this is done in Python.
[02:25] It will be highly technical, but you can still follow,
[02:27] even if you don't have a purely technical or numerical background,
[02:30] because the elements of the code are directly related to trading.
[02:34] I will show you the results and we will discuss how these can be used for our strategies.
[02:39] Since this project is relatively larger than the previous projects or studies
[02:43] published on this channel, I'm not using a Jupyter notebook file this time.
[02:47] I'm using Python files because we're going to use few files like one, two, three,
[02:52] four different Python files.
[02:54] So we're splitting the code into four different files in order to make it easier
[02:58] to read and easier to understand.
[03:00] And then we're going to launch it through Python.
[03:02] So we're not using a Jupyter notebook file in this case.
[03:05] However, when you download it, I will be sharing a folder with the data I
[03:10] would be using for this model.
[03:12] So we can see that we have the Urias dollar candlestick, the hourly data.
[03:17] It's between 2020 and 2023.
[03:21] And then I have another out of sample data or testing data where I've downloaded
[03:26] between 2023 and 2025.
[03:29] So this is the data on which we're going to test the model after we have
[03:33] trained it on the previous three years.
[03:35] I'm going to start with the indicators.py file.
[03:39] So that's a Python file.
[03:41] I'm using pandas and pandas technical analysis.
[03:44] It's just defining one single function here, load and pre-process data.
[03:49] It takes a CSV path.
[03:50] So the path for a CSV file, we're going to read underscore CSV using the path,
[03:55] clean the data, somehow sort the index, add some technical indicators,
[04:00] the RSI 14 moving average 2050 and the ATR, the moving average 20 slope as well.
[04:06] So that's just the difference between two consecutive rows.
[04:09] It's not really the regression slope on three or four rows.
[04:13] So it's not really the slope.
[04:14] It's just a difference between two consecutive moving average values.
[04:19] And then we're dropping the empty values or the empty rows.
[04:23] We return a data frame with few additional indicators.
[04:27] And this is where if you intend to improve this code,
[04:30] this is where we can add some additional indicators and some custom indicators.
[04:35] Maybe you don't want to use the classic indicators.
[04:37] Maybe you want to add your own.
[04:39] But I mean, this is where we can do it.
[04:41] It's in this file.
[04:42] You can define whatever indicators you want as functions here
[04:46] and then use them to return the data frame with these indicators.
[04:50] Now we can define the trading environment.
[04:53] And this is done using importing Jim and NumPy
[04:57] because we're going to use it for numerical analysis or numerical operations.
[05:02] And from Jim, we're also importing spaces,
[05:04] the observation spaces and the action spaces.
[05:07] So these are basically defining the actions that are allowed for the agent.
[05:13] And I'm defining a class named Forex Trading Environment
[05:17] that inherits from Jim.EnvironmentClass
[05:20] because this is how I want to create the environment
[05:22] by inheriting from the package Jim.
[05:26] We define the constructor.
[05:28] Notice that we have a window size by default equal to 30.
[05:32] So by default, the agent is going to read the last 30 candles
[05:38] before taking a decision.
[05:39] And this, of course, includes all the related technical indicators
[05:43] that we've added in the data frame.
[05:45] Now, for the stop loss options,
[05:48] I'm allowing the agent to take one of three decisions,
[05:52] either 60 pips or 90 pips distance or 120 pips.
[05:58] Where do these come from?
[05:59] These are just random.
[06:01] On the EURAS dollar, on the hourly time frame,
[06:04] I would put maybe 60 pips to 90 or 120 pips of stop loss distance.
[06:09] Same thing for the take profit options.
[06:12] So we have 60, 90 and 120.
[06:15] You could add these, you could extend these,
[06:17] but the more options you give to the agent,
[06:22] the more time it's going to take to train the agent
[06:25] and it's going to become computationally more expensive.
[06:28] So it requires more computation time.
[06:30] Now, this shouldn't be a problem, of course,
[06:32] but for the sake of this video,
[06:34] I kept it as simple as possible to show you how it's done.
[06:36] Now, there are three options here for trades,
[06:39] either the action zero,
[06:41] so it means that we're not going to trade.
[06:44] The agent is going to skip the candle
[06:46] without opening any trades.
[06:47] But in the opposite case, if action is positive
[06:51] or it's equal to one,
[06:52] then we have two different directions.
[06:55] Either we short the market
[06:56] or the agent will long the market.
[06:58] So either zero or one.
[07:00] Taking into account, of course,
[07:01] stop loss and take profits.
[07:03] We compute the shapes of the data frame
[07:05] to be used later on by the agent.
[07:07] And this is where we initialize the current step
[07:10] which is equal to zero.
[07:12] At first, we have the equity, $10,000.
[07:15] Maximum slippage is zero for the moment.
[07:18] Then we have the positions list is empty at this point.
[07:23] And at the end, I would like to plot the equity curve.
[07:26] So we're going to log the equity curve values
[07:29] and the last trade information.
[07:31] The function within the class named get observation
[07:36] is simply to return the last window size.
[07:39] Remember that we took 30 by default, 30 rows.
[07:43] So the agent is going to read the last 30 rows
[07:46] but also the number of features.
[07:48] So the shape is going to be window size.
[07:50] It's an umpire array, by the way.
[07:52] So it's two dimensional umpire array
[07:54] with the window size and also accessing all the features
[07:58] available on the data frame.
[08:00] It also takes care of the edge case
[08:02] at the beginning of the data frame
[08:03] when we don't have enough history.
[08:05] So this is going to be used by the agent
[08:08] to read the data before each candle.
[08:11] And now we have to define the calculate reward.
[08:15] Remember that the agent is going to behave
[08:17] just like we are training a pet.
[08:19] Okay, we're training a dog.
[08:20] And we need to provide this reward function
[08:24] to know when we can reward in a positive value
[08:26] or in a negative value, the agent.
[08:29] In this case, we're going to use the profit and loss
[08:32] for each of the trade.
[08:33] So if the agent opens a long position, for example,
[08:36] or any trade and the result
[08:39] of profit and loss is positive,
[08:41] the reward is going to be positive
[08:43] and it's also proportional to the profit and loss value.
[08:47] And that's why at the end of this function,
[08:49] the reward, which is the returned value
[08:52] is the profit and loss times 10,000
[08:55] because it has to be adjusted to the number of pips
[08:58] from the euro as dollar price.
[09:00] In the opposite case, if it's a loss,
[09:02] so if it's negative, in this case,
[09:05] we're going to return a reward that is negative.
[09:07] Now, since data is processed in candles,
[09:12] you might have this extreme case
[09:14] where one candle touches the stop loss
[09:16] and the take profit at the same time.
[09:19] We don't know, since we're not using tick data,
[09:21] we don't know which of these levels were touched first,
[09:25] were triggered first.
[09:26] So we don't know if the trade was a loss or a profit.
[09:31] In this case, just to be on a safe side,
[09:33] we're going to consider it a loss.
[09:35] So we don't cheat our way around.
[09:38] We're going to, in case of a doubt,
[09:40] we're going to consider the trade, it's been a loss,
[09:42] and we're going to return a negative reward as well.
[09:46] And that's it, basically.
[09:47] Now we still have to define one more function.
[09:50] That's the step function.
[09:52] It's going to consider all of the previous functions.
[09:55] So we have direction, stop loss, and a take profit,
[09:58] and the reward, and so on.
[09:59] It's going to crunch it all together.
[10:01] It's going to return the observation,
[10:03] the reward, and other information.
[10:05] The reset function resets the values of the back test.
[10:09] So to the current step and the equity 10,000,
[10:13] and it empties the equity curve list, and so on,
[10:17] to restart the test, actually.
[10:20] And then we can render the equity curve
[10:21] using the render function.
[10:23] So that was our trading environment.py.
[10:25] Now to train the agent,
[10:27] we're going to use all of these functions and classes
[10:30] to make it happen.
[10:32] So we're going to import from stable baseline three,
[10:35] the PPO, that's the model we're going to use
[10:39] to train the agent.
[10:40] And if, again, if you are coming from data science,
[10:44] AI, or reinforcement learning,
[10:45] and you are a bit familiar with these,
[10:47] this is a model-free approach.
[10:50] This means that the agent is going to learn
[10:52] directly from the environment.
[10:53] We don't have the whole environment map in front of us,
[10:56] and we're asking the agent to learn from the map.
[10:59] It's actually going to interact step-by-step
[11:02] with the candles, with the historical data, trial and error,
[11:05] as going to adjust the parameters
[11:08] when it's progressing through the data.
[11:10] So first we're going to load and process the data.
[11:13] I have the euro US dollar, hourly timeframe, 2020, 2023.
[11:17] I'm creating actually an environment.
[11:19] So using the class Forex Trading Environment,
[11:22] providing the data frame, the window size of 30,
[11:26] the stop loss options, which you can change here,
[11:29] the take profit options.
[11:30] Then we have a dummy vector declaration
[11:33] that is required by stable baselines for parallelization.
[11:37] So we're not going to go into the technical details,
[11:40] but this is where you can also experiment to change the PPO.
[11:45] Now, I'm not saying that you will be getting better results.
[11:47] It's just that for learning purposes,
[11:50] for educational purposes,
[11:51] it's good also to train the model using different models
[11:55] or the agent actually, train the agent
[11:58] using different models.
[11:59] The PPO is actually one of the best suited models
[12:04] for this case for financial trading,
[12:07] simply because this is a very noisy and continuous data.
[12:10] So we assume that the data is flowing continuously.
[12:14] The agent is going to receive data
[12:16] live from the market and it will build its skills
[12:20] trading live on the market,
[12:22] checking whenever we have a loss,
[12:23] whenever we have a winning trade and so on.
[12:25] So it's kind of acquiring this experience.
[12:28] And in this case, PPO works well.
[12:30] Then we're going to train the model.
[12:32] So using model.learn, the total,
[12:35] total time steps actually is 50,000.
[12:37] You might want to adjust this one as well.
[12:39] If you increase it,
[12:40] it's going to train the model more in a better way,
[12:44] but it requires also,
[12:45] it requires also additional computational power.
[12:49] Then we can save the model
[12:50] as model underscore Uri as dollar.
[12:53] And that's the zip file you can see here.
[12:54] I've already run and trained the model
[12:57] and I've saved it here for later to be used.
[13:00] And at the end, we print model saved successfully.
[13:04] Then we can evaluate or test the model.
[13:07] So we're going to reset the environment.
[13:10] The equity curve is empty again.
[13:12] And then we're going to try to predict,
[13:13] use the model to predict values
[13:15] using the observation space.
[13:16] We don't have any stochastic operations included.
[13:20] So that's deterministic.
[13:22] And for each step,
[13:24] we're going to apply the action,
[13:26] buying or selling and so on.
[13:28] We're going to record the observation,
[13:31] the reward and if it's done or not.
[13:33] So if it's finished or not
[13:35] and some additional information.
[13:37] And at the end, I'm going to append the equity
[13:40] with the current equity actually.
[13:42] So that's going to build our equity curve.
[13:45] So we're going to append all the equity values
[13:47] or the balance values in the equity curve list
[13:50] to be able to plot it using this part of the file.
[13:54] We're able to run this.
[13:56] I will be opening a new terminal.
[13:58] I'm going to source my environment
[14:01] because I've created a virtual environment
[14:02] specifically for this application.
[14:04] Virtual environment scripts activate.
[14:07] I'm going to run python train agent dot pi.
[14:12] And I'm going to run it.
[14:14] So it's going to take a while before it finishes.
[14:18] So as you can see, you can follow up what's happening.
[14:20] The lapse time, the learning rate, the loss value.
[14:24] And once this is done,
[14:25] it's going to plot the equity curve on the training data.
[14:28] And as you can see, it's training well.
[14:30] So it's managing to increase the equity.
[14:35] Which means that basically the agent knows
[14:38] that it needs to follow the positive rewards action
[14:41] or course of actions.
[14:43] So it's building a kind of policy
[14:44] that will allow the equity to increase over time
[14:48] with the different trades.
[14:49] Now the correct way to evaluate the agent
[14:52] is actually to test it on new and unseen data.
[14:54] This is the training data and it's working well.
[14:57] We can see that the equity is positive.
[14:59] The agent is heading in the correct direction.
[15:02] Let's close this one and head to the test agent dot pi file.
[15:07] And here I'm loading a new unseen data.
[15:10] So that's always the Urias dollar candlesticks one hour timeframe.
[15:15] But this time it's 2020 up to 2025.
[15:18] I'm not going to train the model here.
[15:21] It's not going to fit or apply any fitting.
[15:23] It's just going to try and trade.
[15:25] But I'm still using the same options
[15:27] for stop loss and take profits.
[15:29] The same window size as what we have used
[15:32] for the training part.
[15:34] And I'm going to run this same model.
[15:36] So we're loading the model that we have saved
[15:39] from the training phase or the learning phase.
[15:42] And we're going to try and test the agent.
[15:47] So Python test agent dot pi.
[15:51] It also takes a bit of time
[15:53] before showing the equity curve.
[15:55] And this is what we're getting.
[15:56] So it's not what we've expected.
[15:59] The equity was showing a more positive trend
[16:03] using the training steps or the training data.
[16:06] But this is on you and unseen data.
[16:09] It's not very bad either.
[16:10] Because to be honest,
[16:11] we didn't provide much for the for the agent.
[16:14] So these are barely few technical indicators.
[16:17] These are classic technical indicators,
[16:19] two moving averages, DRSI, the ATR
[16:22] and what we're calling a slope,
[16:24] which is not really a slope within an apply aggression.
[16:27] This is just to show you an example
[16:29] as simple as possible.
[16:31] Actually, just for the sake of this video.
[16:33] But in this function,
[16:34] you might want to think
[16:36] how you can add additional technical indicators
[16:39] that matter for the trading,
[16:40] that matter for the agent
[16:42] that can provide additional and valuable information
[16:45] for the agent to learn how to trade.
[16:47] One thing also that we could be changing
[16:50] in the trading environment,
[16:53] these options.
[16:54] So I've also provided very limited options
[16:58] for the stop loss and take profit values.
[17:00] So it's either 60, 90 or 120 pips for both.
[17:03] Maybe this is not enough for trading the URIAS dollar.
[17:06] Maybe we should be providing more values,
[17:09] maybe with five pips of increments,
[17:11] covering from 30 pips up to I would say 100 pips,
[17:15] for example, for both stop loss and take profit options.
[17:19] So that's one thing to be improved.
[17:21] Also, when we were training the agent,
[17:23] we used 50,000 time steps.
[17:26] Maybe the agent is overfitting.
[17:28] We could try to fit it with 10,000 steps, for example.
[17:32] So now if I'm interrupting and retraining with 10,000 steps,
[17:39] I'm going to show you, let me save it first.
[17:42] So I'm going to show you the effect
[17:44] of this small parameter.
[17:47] So I just switched from 50,000 time steps
[17:50] of training down to 10,000 time steps.
[17:54] And this is the training equity again.
[17:56] It's working well.
[17:57] Now we can test the model.
[17:59] The equity that we're going to get is slightly different.
[18:02] So as you can see, it's kind of positive.
[18:06] At first it's not as positive later on and so on.
[18:09] So sometimes you might get the set of parameters
[18:12] that will allow you to train the model,
[18:15] but then test it also on unseen data.
[18:17] And you can still have this positive equity trend,
[18:21] even when you are testing on unseen data.
[18:23] So as you may have noticed, there's a lot of options
[18:26] that we can still use to improve the trading agent potential.
[18:31] I still find it enjoyable, to be honest,
[18:34] adding some more stop-loss options, take profit options,
[18:38] and trading indicators, maybe the classic
[18:40] or custom indicators and so on,
[18:42] changing the total time steps
[18:45] in order to avoid overfitting the model
[18:47] on the training data and so on.
[18:49] So it's a lot of fun and seeing the results
[18:52] straight in front of us is also powerful
[18:54] because you can see the effects
[18:55] immediately in front of you.
[18:57] And that will be it for this video.
[18:59] I hope you guys liked it and found the information helpful.
[19:02] I've been receiving lots of requests recently.
[19:05] Why don't we use the reinforcement learning and trading?
[19:08] As you may have noticed, it's very powerful.
[19:10] It has a lot of potential,
[19:11] but it's not as simple to fine-tune as well
[19:14] because you have a lot of noise in the trading data.
[19:18] So this is the nature of the market.
[19:20] And sometimes the model is finding it difficult
[19:24] to pick up the signal, the true signal of the trend
[19:27] from all the noise that you can find in the data.
[19:30] But anyway, I hope you guys liked it.
[19:32] I hope you found this information helpful.
[19:34] If so, please leave a like, leave a comment,
[19:36] drop your ideas in the comments section.
[19:38] This was requested by one of the viewers
[19:41] through the comments section.
[19:42] So don't hesitate to drop us some of your ideas.
[19:45] Thank you so much for watching.
[19:46] Thank you so much for staying that long.
[19:49] Until our next one, trade safe and see you next time.
