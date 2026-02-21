// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract StudentRegistry {
    struct Record {
        string studentId;
        string dataHash;      // The SHA-256 fingerprint of the inputs
        string prediction;    // "Placed" or "Not Placed"
        uint256 timestamp;
    }

    mapping(string => Record) private records;
    
    event RecordVerified(string studentId, string dataHash, string prediction);

    // Stores the prediction result and data fingerprint on the blockchain
    function storeRecord(string memory _studentId, string memory _dataHash, string memory _prediction) public {
        records[_studentId] = Record({
            studentId: _studentId,
            dataHash: _dataHash,
            prediction: _prediction,
            timestamp: block.timestamp
        });

        emit RecordVerified(_studentId, _dataHash, _prediction);
    }

    // Returns the data hash and prediction for verification
    function getRecord(string memory _studentId) public view returns (string memory, string memory, uint256) {
        Record memory r = records[_studentId];
        return (r.dataHash, r.prediction, r.timestamp);
    }
}