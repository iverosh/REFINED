import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms
from Quanv2d import Quanv2d
from tqdm import tqdm
from torch.utils.data import DataLoader
from torch.utils.data import Dataset
import matplotlib.pyplot as plt
import os
from qiskit import QuantumCircuit
from torchvision.io import read_image
from qiskit.circuit import Parameter
import random
import itertools
import numpy as np
import pandas as pd
from typing import Union, List, Iterator

class MyQuanv2d(Quanv2d):
    def __init__(self,input_channel,output_channel,num_qubits,num_weight,kernel_size = 3,stride = 1):
        super().__init__(input_channel, output_channel, num_qubits, num_weight, kernel_size, stride)
    def build_circuit(self,num_weights : int,num_input : int,num_qubits : int = 3):
        qc = QuantumCircuit(num_qubits)
        weight_params = [Parameter('w{}'.format(i)) for i in range(num_weights)]
        input_params = [Parameter('x{}'.format(i)) for i in range(num_input)]
        for i in range(num_qubits):
            qc.h(i)
        q_index = 0
        for i in range(0,num_input,3):
            qc.rz(input_params[i],q_index)
            if i+1 < num_input:
                qc.ry(input_params[i+1],q_index)
            if i+2 < num_input:
                qc.rz(input_params[i+2],q_index)
            q_index += 1
            if q_index == num_qubits:
                q_index = 0
                for j in range(num_qubits):
                    qc.cx(j, (j + 1)%num_qubits)

        for i in range(0,num_weights,3):
            #check if i+1 and i+2 is out of range
            qc.rz(weight_params[i],q_index)
            if i+1 < num_weights:
                qc.ry(weight_params[i+1],q_index)
            if i+2 < num_weights:
                qc.rz(weight_params[i+2],q_index)
            q_index += 1
            if q_index == num_qubits:
                q_index = 0
                for j in range(num_qubits):
                    qc.cx(j, (j + 1)%num_qubits)
        
        if q_index != 0:
            for i in range(q_index,num_qubits):
                qc.cx(i, (i + 1)%num_qubits)
        # #entangle the qubits
        # for i in range(num_qubits):
        #     qc.cx(i, (i + 1)%num_qubits)
        print(qc)
        return qc, weight_params, input_params
    
class HybridQNN(nn.Module):
    '''
    A hybrid quantum convolutional neural network
    constucted by a classical convolutional layer and a quantum convolutional layer
    '''
    def __init__(self):
        super(HybridQNN, self).__init__()
        #build a full classical convolutional layer
        '''
        write the layer needed for the model
        '''
        self.conv1 = nn.Conv2d(4, 1, 3)
        self.bn1 = nn.BatchNorm2d(1)
        self.sigmoid = nn.Sigmoid()
        self.maxpool1 = nn.MaxPool2d(2)
        self.conv2 = MyQuanv2d(1, 2, 3, 9,kernel_size=3,stride=3)
        self.bn2 = nn.BatchNorm2d(2)
        self.relu2 = nn.ReLU()
        self.maxpool2 = nn.MaxPool2d(2)
        self.flatten = nn.Flatten()
        self.linear = nn.Linear(18, 1) 

    def forward(self, x: torch.Tensor)-> torch.Tensor:
        '''
        forward function for the model
        args
            x: input tensor
        return
            x: output tensor
        '''
        '''
        write the forward function for the model
        default as 
        HybridQNN(
            (conv1): Conv2d(1, 1, kernel_size=(3, 3), stride=(1, 1))
            (bn1): BatchNorm2d(1, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True)
            (sigmoid): Sigmoid()
            (maxpool1): MaxPool2d(kernel_size=2, stride=2, padding=0, dilation=1, ceil_mode=False)
            (conv2): Quanv2d(
                (qnn): TorchConnector()
            )
            (bn2): BatchNorm2d(2, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True)
            (relu2): ReLU()
            (maxpool2): MaxPool2d(kernel_size=2, stride=2, padding=0, dilation=1, ceil_mode=False)
            (flatten): Flatten(start_dim=1, end_dim=-1)
            (linear): Linear(in_features=32, out_features=10, bias=True)
        )
        '''
        
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.sigmoid(x)
        x = self.maxpool1(x)
        x = self.conv2(x)
        x = self.bn2(x)
        x = self.relu2(x)
        x = self.flatten(x)
        x = self.linear(x)
        return x

# Define the training function

def train(
        model:nn.modules,
        device:torch.device, 
        train_loader: DataLoader, 
        optimizer:optim.Optimizer, 
        criterion: nn.Module
        )->tuple[float, float, nn.Module]:
    '''
    basic train function generate by github-copilot
    args
        device: device to train the model
        train_loader: training data loader
        optimizer: optimizer for the model
        criterion: loss function    
    return
        train_loss: loss of the training process
        accuracy: accuracy of the training process
        model: trained model
    '''
    model.train()
    train_loss = 0
    pbar = tqdm(train_loader)
    for batch_idx, (data, target) in enumerate(pbar):
        data, target = data.to(device), target.to(device)
        optimizer.zero_grad()
        output = model(data)
        loss = criterion(output, target)
        loss.backward()
        optimizer.step()
        train_loss += loss.item()
        pbar.set_description(desc=f'Train Loss={train_loss/len(train_loader.dataset ):.4f}'+
                                  f'|Batch_id={batch_idx}'
                                  )
    # train_loss /= len(train_loader.dataset)
    train_loss /= len(train_loader.dataset)
    return train_loss, model  

# Define the test function
def test(
        model:nn.modules, 
        device:torch.device, 
        test_loader:DataLoader, 
        criterion:nn.Module
        )->tuple[float, float]:
    '''
    basic test function generate by github-copilot
    args
        device: device to train the model
        test_loader: test data loader
        criterion: loss function
    return
        test_loss: loss of the test process
        accuracy: accuracy of the test process
    '''
    model.eval()
    test_loss = 0
    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)
            output = model(data)
            test_loss += criterion(output, target).item()
    test_loss /= len(test_loader.dataset)
    return test_loss



def Train_Hybrid_QNN(Net : nn.Module,
                     optimizer : optim.Optimizer,
                     criterion : nn.Module,
                     train_dataset : datasets,
                     test_dataset : datasets,
                     **kwargs) -> None:
    '''
    Train a HybridQNN model
    args
        Net: HybridQNN
        optimizer: optimizer for the model
        criterion: loss function
        train_dataset: training dataset
        test_dataset: test dataset
        kwargs: hyperparameters
    return
        None
    Save
        model: trained model (to data/{model_name}/{model_path})
        results: results of the training process (to data/{model_name}/results.pt)
        accuracy.png: plot of the accuracy (to data/{model_name}/accuracy.png)
        loss.png: plot of the loss (to data/{model_name}/loss.png)
    '''
    defaule_kwargs = {'legnth':500,
                      'batch_size':50,
                      'epochs':10,
                      'model_name':'HybridQNN',
                      'model_path':'model.pt',
                      'learning_rate':0.01,
                      'mode':'new_model',
                      'seed':0}
    
    for key in kwargs:
        if key in defaule_kwargs:
            defaule_kwargs[key] = kwargs[key]
        else:
            raise ValueError(f'key {key} not in defaule_kwargs')
        
    legnth = defaule_kwargs['legnth']
    batch_size = defaule_kwargs['batch_size']
    epochs = defaule_kwargs['epochs']
    model_name = defaule_kwargs['model_name']
    model_path = defaule_kwargs['model_path']
    learning_rate = defaule_kwargs['learning_rate']
    mode = defaule_kwargs['mode']

    torch.manual_seed(seed)
    #make directory
    os.makedirs(f'data/{model_name}',exist_ok=True)
    #load data
    # train_dataset.data = train_dataset.data[:legnth]
    # train_dataset.targets = train_dataset.targets[:legnth]
    # test_dataset.data = test_dataset.data[:int(legnth/5.1)]
    # test_dataset.targets = test_dataset.targets[:int(legnth/5.1)]

    # Create the data loaders
    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, shuffle=True)

    # Set the device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # Initialize the model and move it to the device

    model = Net().to(device)
    if mode == 'old_model':
        model.load_state_dict(torch.load(f'data/{model_name}/{model_path}'))
        #load results
        results = torch.load(f'data/{model_name}/results.pt')
    else:
        results = {'train_loss':[],'test_loss':[],'best_loss':1e5}
        #check if the model exists
        if os.path.exists(f'data/{model_name}/{model_path}'):
            check = input('model exists, press enter to overwrite(y/n)')
            if check == 'n' or check == 'N':
                build = input('build a new model?(y/n)')
                if build == 'n' or build == 'N':
                    raise ValueError('model exists')
                elif build == 'y' or build == 'Y':
                    model_name = f'{model_name}_{random.randint(0,100)}'
                    os.makedirs(f'data/{model_name}',exist_ok=True)
                    print(f'new model name: {model_name}')
                else:
                    raise ValueError('invalid input')
            elif check == 'y' or check == 'Y':
                pass
            else:
                raise ValueError('invalid input')

    print(model)

    # Define the optimizer and loss function
    optimizer = optimizer(model.parameters(), lr=learning_rate)

    # Train the model
    if epochs > 0:
        for epoch in range(1, epochs + 1):
            print(f'epoch : {epoch}')
            train_loss, model = train(model,device, train_loader, optimizer, criterion)
            test_loss = test(model, device, test_loader, criterion)
            results['train_loss'].append(train_loss)
            results['test_loss'].append(test_loss)
            if test_loss < results['best_loss']:
                results['best_loss'] = test_loss
                #save the model for future use
                torch.save(model.state_dict(), f'data/{model_name}/{model_path}')
            #save results
            torch.save(results,f'data/{model_name}/results.pt')
            print('Epoch: {} Test Loss: {:.4f}'.format(epoch, test_loss))
    elif epochs == 0:
        pass
    else:
        raise ValueError('invalid epochs')

    #plot the loss 
    plt.plot(results['train_loss'],label='train_loss')
    plt.plot(results['test_loss'],label='test_loss')
    plt.title('Loss')
    plt.legend()
    plt.savefig(f'data/{model_name}/loss.png')
    plt.clf()
    
class CustomDataset(Dataset):
    def __init__(self, data_dir, targets, transform=None):
        self.data_dir = data_dir
        self.targets = targets
        self.transform = transform
        self.images = os.listdir(data_dir)

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img_name = os.path.join(self.data_dir, self.images[idx])
        image = read_image(img_name).to(torch.float)
        
        if self.transform:
            image = self.transform(image)
        
        target = self.targets[idx]
        
        return image, target


targets = pd.read_csv("C:\\Users\\vanek\\Desktop\\diplom\\REFINED\\data\\phenotype_28042016_synchro.csv", usecols=[9])
targets = targets.values.astype(float)
print(len(targets))



dataset = CustomDataset("REFINED\\images", targets)


#some hyperparameters
legnth = 500
batch_size = 20
epochs = 15
model_name = 'HybridQCNN'
model_path = 'HQCNN.pt'
learning_rate = 0.01
mode = 'new_model'
seed = 999

train_dataset, test_dataset = torch.utils.data.random_split(dataset, [int(len(dataset) * 0.8), len(dataset) - int(len(dataset) * 0.8)])
# print(len(train_dataset))
# print(len(test_dataset))
optimizer = optim.Adam
criterion = nn.L1Loss()
Net = HybridQNN
# Train_Hybrid_QNN(Net,optimizer,criterion,train_dataset,test_dataset,
#                     legnth=legnth,batch_size=batch_size,epochs=epochs,
#                     model_name=model_name,model_path=model_path,learning_rate=learning_rate,mode=mode,seed=seed)

