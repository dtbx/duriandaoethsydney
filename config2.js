import {
    CultureIndexMediaType,
    CultureIndexRequiredMediaPrefix,
  } from "@cobuild/libs/web3/revolution/types";
  import { RevolutionDeployArgs } from "../../types/RevolutionBuilder";
  
  export const args: RevolutionDeployArgs = [
    //initial owner
    "0x6911c30f0E6F26e464dd5aaC032AF17c7482fd51", // Durian DAO team multisig:
    //base weth address
    "0x4200000000000000000000000000000000000006",
    //revolution token
    {
      name: "DurianDAO",
      symbol: "DUR",
      contractURIHash: "ipfs://QmUqA276B3e5ELzTfHfivtcnhHRqHesJp7Rinq8iac6gEm", // to chat with Rocketmen vrbs collection URI
      tokenNamePrefix: "Durian",
    },
    //auction
    {
      timeBuffer: BigInt(300), // 5 minutes
      reservePrice: BigInt(1), // not 0
      duration: BigInt(86400), // 1 day
      minBidIncrementPercentage: 2, // 2%
      minCreatorRateBps: BigInt(250), // 2.5%
      creatorRateBps: BigInt(4000), // 40%
      entropyRateBps: BigInt(5000), // 50% - so 10/10 votes/eth
      grantsParams: {
        totalRateBps: BigInt(0),
        grantsAddress: "0x6911c30f0E6F26e464dd5aaC032AF17c7482fd51", // multisig for Durian DAO should be ( architects multisig on Base)
      },
    },
    //dao
    {
      // TODO revisit https://etherscan.io/tx/0x4e064817c4fac01d46e35bc6250da7d858a2101195baf2be6da435498984d6c4#eventlog
      // seconds
      timelockDelay: BigInt(172800), // 2 days
      // blocks
      votingDelay: BigInt(129600), // nouns is 21600 blocks (delay + update period), base block time is 2s, eth is 12s so 21600 * 6
      // blocks
      votingPeriod: BigInt(172800), // nouns is 28800 blocks, base block time is 2s, eth is 12s so 28800 * 6
      // how much you need to make a proposal
      proposalThresholdBPS: BigInt(50), // 0.5% to start, can bring down after treasury grows
      vetoer: "0x6911c30f0E6F26e464dd5aaC032AF17c7482fd51", // DAO Multisig architects multisig on Base
      name: "Durian DAO",
      flag: "💥",
      purpose:
        // "Enjoy your day, eat durian. Plant trees for public good benefits. Durian lovers of all nations and species are welcome, everyone is a creator and there's always a better way. Live, love, laugh and learn, the cyberwilderness will reward you for your creativity."
      dynamicQuorumParams: {
        minQuorumVotesBPS: 1000,
        maxQuorumVotesBPS: 1500,
        quorumCoefficient: 1000000,
      },
    },
    //culture index
    {
      name: "Durian Art Race",
      description: "Create the next Durian. Become a part of Stinky history.",
      template: "ipfs://QmRH5Ht68hk6wEYCndCey2SCXDxgpf5B6qAGCZy4Ah9zxG",
      checklist: `
  Art should include durian and noggles 
  `,
      tokenVoteWeight: BigInt(1e18 * 1000),
      pointsVoteWeight: BigInt(1),
      pieceMaximums: {
        name: BigInt(210),
        description: BigInt(2_000),
        image: BigInt(64_000),
        text: BigInt(100_000),
        animationUrl: BigInt(1_000),
      },
      quorumVotesBPS: BigInt(250), // 2.5%
      minVotingPowerToCreate: BigInt(0),
      minVotingPowerToVote: BigInt(1),
      requiredMediaType: CultureIndexMediaType.IMAGE,
      requiredMediaPrefix: CultureIndexRequiredMediaPrefix.SVG, // mention the file formats acceptable, png or animated files
    },
    //revolution points
    {
      tokenParams: { name: "Pungency", symbol: "PULP" },
      emitterParams: {
        // Start out expensive and don't decay too quickly if behind schedule
        // We want to incentivize people to bid on the auction
        vrgdaParams: {
          targetPrice: BigInt(1 * 1e14), // 0.0001 ETH
          priceDecayPercent: BigInt(1.5 * 1e17), // 15% per day scaled by 1e18
          tokensPerTimeUnit: BigInt(1000 * 1e18), // 1000 tokens per day scaled by 1e18
        }, // decayRate, targetPrice, perTimeUnit
        grantsParams: {
          totalRateBps: BigInt(0),
          grantsAddress: "0x6911c30f0E6F26e464dd5aaC032AF17c7482fd51", // architects multisig on Base
        },
        founderParams: {
          founderAddress: "0x6911c30f0E6F26e464dd5aaC032AF17c7482fd51", // architects multisig on Base
          totalRateBps: BigInt(1500), // 15% founder rate
          entropyRateBps: BigInt(5000), // 50% entropy
          rewardsExpirationDate: BigInt(1804262212), // Friday March 3rd, 2027 - 3 yrs
        },
      },
    },
    //voting power
    {
      tokenVoteWeight: BigInt(1e18 * 1000),
      pointsVoteWeight: BigInt(1),
    },
  ];