//SPDX-License-Identifier: MIT
pragma solidity ^0.8.7;

import {Chainlink, ChainlinkClient} from "@chainlink/contracts/src/v0.8/ChainlinkClient.sol";
import {ConfirmedOwner} from "@chainlink/contracts/src/v0.8/shared/access/ConfirmedOwner.sol";
import {LinkTokenInterface} from "@chainlink/contracts/src/v0.8/shared/interfaces/LinkTokenInterface.sol";

contract Libertai is ChainlinkClient, ConfirmedOwner {
    using Chainlink for Chainlink.Request;

    mapping(bytes32 => string) public requests;
    mapping(string => string) public completions;

    bytes32 private jobId;
    uint256 private fee;

    event RequestReceived(bytes32 indexed requestId, string indexed requestCid);
    event RequestFulfilled(
        bytes32 indexed requestId,
        string indexed requestCid,
        string indexed responseCid
    );

    /**
     * @notice Initialize the link token and target oracle
     * @dev The oracle address must be an Operator contract for multiword response
     *
     *
     * Sepolia Testnet details:
     * Link Token: 0x779877A7B0D9E8603169DdbD7836e478b4624789
     * Oracle: 0x6090149792dAAeE9D1D568c9f9a6F6B46AA29eFD (Chainlink DevRel)
     * jobId: 7da2702f37fd48e5b1b9a5715e3509b6
     *
     */
    constructor() ConfirmedOwner(msg.sender) {
        _setChainlinkToken(0x779877A7B0D9E8603169DdbD7836e478b4624789);
        _setChainlinkOracle(0x6090149792dAAeE9D1D568c9f9a6F6B46AA29eFD);
        jobId = "7d80a6386ef543a3abb52817f6707e3b";
        fee = (1 * LINK_DIVISIBILITY) / 10;
    }

    /**
     * @notice Request variable bytes from the oracle
     */
    function requestCompletion(string memory requestCid) public {
        Chainlink.Request memory req = _buildChainlinkRequest(
            jobId,
            address(this),
            this.fulfillCompletion.selector
        );
        req._add(
            "get",
            string.concat(
                "https://aleph-oracle.rphi.xyz/completion/ipfs?cid=",
                requestCid
            )
        );
        req._add("path", "cid");
        bytes32 requestId = _sendChainlinkRequest(req, fee);
        requests[requestId] = requestCid;
        emit RequestReceived(requestId, requestCid);
    }

    /**
     * @notice Fulfillment function for variable bytes
     * @dev This is called by the oracle. recordChainlinkFulfillment must be used.
     */
    function fulfillCompletion(
        bytes32 requestId,
        string memory responseCid
    ) public recordChainlinkFulfillment(requestId) {
        string memory requestCid = requests[requestId];
        completions[requestCid] = responseCid;
        emit RequestFulfilled(requestId, requestCid, responseCid);
    }

    function withdrawLink() public onlyOwner {
        LinkTokenInterface link = LinkTokenInterface(_chainlinkTokenAddress());
        require(
            link.transfer(msg.sender, link.balanceOf(address(this))),
            "Unable to transfer"
        );
    }
}
